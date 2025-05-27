from typing import Annotated

import typer
from git import Commit, GitCommandError, InvalidGitRepositoryError
from github import Auth, Github, GithubException

from jira import JIRA

from glu.ai import generate_description, prompt_for_chat_provider
from glu.config import (
    GITHUB_PAT,
    JIRA_SERVER,
    EMAIL,
    JIRA_API_TOKEN,
    JIRA_READY_FOR_REVIEW_TRANSITION,
    JIRA_IN_PROGRESS_TRANSITION,
)
from glu.gh import prompt_for_reviewers
from glu.utils import (
    print_error,
)
from glu.git import (
    get_repo_name,
    get_repo,
    get_first_commit_since_checkout,
    remote_branch_in_sync,
)
from glu.jira import format_jira_ticket, get_jira_project

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
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            "-pr",
            help="AI model provider",
        ),
    ] = None,
):
    try:
        git = get_repo()
        repo_name = get_repo_name(git)
    except InvalidGitRepositoryError:
        print_error("Not valid a git repository")
        raise typer.Exit(1)

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

    jira_key = get_jira_project(jira, repo_name, project) if ticket else ""

    title = first_commit.summary
    body = _create_pr_body(first_commit, jira_key, ticket)

    selected_reviewers = prompt_for_reviewers(gh, reviewers, repo_name, draft)

    chat_provider = prompt_for_chat_provider(provider)

    pr = repo.create_pull(
        repo.default_branch,
        git.active_branch.name,
        title=title,
        body=body or "",
        draft=draft,
    )
    pr.add_to_assignees(gh.get_user().login)

    if selected_reviewers:
        for selected_reviewer in selected_reviewers:
            try:
                pr.create_review_request(selected_reviewer.login)
            except GithubException as e:
                print_error(f"Failed to add reviewer {selected_reviewer.login}: {e}")

    rich.print("[grey70]Generating description...[/]")
    pr_description = generate_description(gh, repo, pr, chat_provider)
    if pr_description:
        pr.edit(body=pr_description)

    rich.print(
        f":rocket: Created PR in [blue]{repo_name}[/] with title [bold green]{title}[/]"
    )
    rich.print(f"\n[grey70]{pr_description}[/]\n")

    if not ticket:
        return

    ticket_id = format_jira_ticket(jira_key, ticket)

    transitions = [transition["name"] for transition in jira.transitions(ticket_id)]

    if JIRA_IN_PROGRESS_TRANSITION in transitions:
        jira.transition_issue(ticket_id, JIRA_IN_PROGRESS_TRANSITION)

    if (
        not draft
        and ready_for_review
        and JIRA_READY_FOR_REVIEW_TRANSITION in transitions
    ):
        jira.transition_issue(ticket_id, JIRA_READY_FOR_REVIEW_TRANSITION)
        rich.print(
            f":eyes: Moved issue [blue]{ticket_id}[/] to [green]Ready for review[/]"
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
        return f"[{ticket_str}]"

    if ticket_str in body:
        return body

    return body.replace(ticket, f"[{ticket_str}]")
