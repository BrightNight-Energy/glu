from typing import Annotated

import typer
from InquirerPy import inquirer
from InquirerPy.base import Choice
from git import Commit, GitCommandError
from github import Auth, Github
from github.PullRequest import PullRequest
from github.Repository import Repository
import datetime as dt

from jira import JIRA
from thefuzz import fuzz

from glu import ROOT_DIR
from glu.config import (
    GITHUB_PAT,
    JIRA_SERVER,
    EMAIL,
    JIRA_API_TOKEN,
    JIRA_READY_FOR_REVIEW_TRANSITION,
    JIRA_IN_PROGRESS_TRANSITION,
)
from glu.github import get_members
from glu.models import MatchedUser
from glu.utils import (
    print_error,
)
from glu.git import (
    get_repo_name,
    get_repo,
    get_first_commit_since_checkout,
    remote_branch_in_sync,
)
from glu.jira import format_jira_ticket, get_jira_key
from langchain_glean.chat_models import ChatGlean
from langchain_core.messages import HumanMessage
import rich

app = typer.Typer()


@app.command(short_help="Create a PR with description and transition JIRA ticket")
def create(
    ticket: Annotated[
        str | None,
        typer.Option("--ticket", "-t", help="Jira ticket number", prompt=True),
    ] = None,
    project: Annotated[
        str | None,
        typer.Option(
            "--project", "-p", help="Jira project (defaults to default Jira project)"
        ),
    ] = None,
    draft: Annotated[
        bool, typer.Option("--draft", "-d", help="Mark as draft PR")
    ] = False,
    ready_for_review: Annotated[
        bool, typer.Option(help="Transition ticket to Ready for review")
    ] = True,
    reviewers: Annotated[
        list[str] | None,
        typer.Option(
            "--reviewer",
            "-r",
            help="Requested reviewers (accepts multiple values)",
            show_default=False,
        ),
    ] = None,
):
    repo_name = get_repo_name()
    git = get_repo()

    if git.is_dirty():
        typer.confirm(
            "You have uncommitted changes. Proceed with PR creation?", abort=True
        )

    try:
        git.remotes["origin"].fetch(git.active_branch.name, prune=True)
    except GitCommandError:
        git.git.push("origin", git.active_branch.name)

    if not remote_branch_in_sync(git.active_branch.name, repo=git):
        confirm_push = typer.confirm(
            "Local branch is not up to date with remote. Push to remote now?"
        )
        if confirm_push:
            git.git.push("origin", git.active_branch.name)

    auth = Auth.Token(GITHUB_PAT)
    gh = Github(auth=auth)

    jira = JIRA(JIRA_SERVER, basic_auth=(EMAIL, JIRA_API_TOKEN))

    repo = gh.get_repo(repo_name)

    first_commit = get_first_commit_since_checkout()

    jira_key = get_jira_key(jira, repo_name, project) if ticket else ""

    title = first_commit.summary
    body = _create_pr_body(first_commit, jira_key, ticket)

    pr = repo.create_pull(
        repo.default_branch,
        git.active_branch.name,
        title=title,
        body=body or "",
        draft=draft,
    )
    pr.add_to_assignees(gh.get_user().login)

    if not draft:
        members = get_members(gh, repo_name)
        if reviewers:
            selected_reviewers = []
            for i, reviewer in enumerate(reviewers):
                matched_reviewers = [
                    MatchedUser(member, fuzz.ratio(reviewer, member.login))
                    for member in members
                ]
                sorted_reviewers = sorted(
                    matched_reviewers, key=lambda x: x.score, reverse=True
                )
                if sorted_reviewers[0].score == 100:  # exact match
                    selected_reviewers.append(sorted_reviewers[0].user)
                    continue

                selected_reviewer = inquirer.select(
                    f"Select reviewer{f' #{i + 1}' if len(reviewers) > 1 else ''}:",
                    [
                        Choice(reviewer.user, reviewer.user.login)
                        for reviewer in sorted_reviewers[:5]
                    ],
                ).execute()
                selected_reviewers.append(selected_reviewer)
        else:
            selected_reviewers = inquirer.select(
                "Select reviewers:",
                [Choice(member, member.login) for member in members],
                multiselect=True,
                max_height=5,
            ).execute()

        pr.create_review_request([reviewer.login for reviewer in selected_reviewers])

    pr_description = _generate_description(gh, repo, pr)
    pr.edit(body=pr_description)

    rich.print(
        f"Created PR in [red]{repo_name}[/] with title [bold green]{title}[/] :rocket:"
    )
    rich.print(f"\n[grey]{pr_description}[/]")

    if not ticket:
        return

    ticket_str = format_jira_ticket(jira_key, ticket)

    transitions = [transition.name for transition in jira.transitions(ticket_str)]

    if JIRA_IN_PROGRESS_TRANSITION in transitions:
        jira.transition_issue(ticket_str, JIRA_IN_PROGRESS_TRANSITION)

    if not draft and ready_for_review:
        jira.transition_issue(ticket_str, JIRA_READY_FOR_REVIEW_TRANSITION)
        rich.print(
            f"Moved issue [blue]{ticket_str}[/] to [green]Ready for review[/] :eyes:"
        )


def _create_pr_body(commit: Commit, jira_key: str, ticket: str | None) -> str | None:
    commit_message = (
        commit.message if isinstance(commit.message, str) else commit.message.decode()
    )
    try:
        body = (
            commit_message.replace(
                commit.summary
                if isinstance(commit.summary, str)
                else commit.summary.decode(),
                "",
            )
            .lstrip()
            .rstrip()
        )
    except IndexError:
        body = None

    if not ticket:
        return body

    ticket_str = format_jira_ticket(jira_key, ticket)
    if not body:
        return ticket_str

    if ticket_str in body:
        return body

    return body.replace(ticket, ticket_str)


def _generate_description(gh: Github, repo: Repository, pr: PullRequest) -> str:
    chat = ChatGlean()

    template_dir = ".github/pull_request_template.md"
    try:
        template_file = repo.get_contents(template_dir, ref="main")
        if isinstance(template_file, list):
            template = None
        else:
            template = template_file.decoded_content.decode()
    except Exception:
        template = None

    if not template:
        with open(ROOT_DIR / template_dir, "r", encoding="utf-8") as f:
            template = f.read()

    instructions = """
        Be concise and informative about the contents of the PR, relevant to someone
        reviewing the PR.
    """

    # informs whether to provide the diff or a URL (since indexing should be done)
    is_newly_created_pr = dt.datetime.now(
        dt.timezone.utc
    ) - pr.created_at > dt.timedelta(minutes=15)

    pr_location = "diff below" if is_newly_created_pr else pr.html_url

    pr_diff_str = ""
    if is_newly_created_pr:
        headers = {"Accept": "application/vnd.github.v3.diff"}
        status, _, diff = gh._Github__requester.requestBlob(  # type: ignore
            "GET", pr.url, headers=headers
        )

        if status != 200:
            print_error(f"Failed to get PR diff ({status})")
            raise typer.Exit(1)

        pr_diff_str = f"PR diff:\n{diff}"

    response = chat.invoke(
        [
            HumanMessage(
                content=f"""
        Provide a description for the PR {pr_location} in the following format:
        {template}

        {instructions}

        {pr_diff_str}
        """
            )
        ]
    )

    return response.content  # type: ignore
