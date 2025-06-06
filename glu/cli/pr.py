import re
from typing import Annotated

import rich
import typer
from git import Commit, GitCommandError, InvalidGitRepositoryError
from github import Auth, Github, GithubException
from InquirerPy import inquirer
from jira import JIRA, JIRAError

from glu.ai import (
    generate_commit_message,
    generate_description,
    generate_final_commit_message,
    prompt_for_chat_provider,
)
from glu.config import (
    DEFAULT_JIRA_PROJECT,
    EMAIL,
    GITHUB_PAT,
    JIRA_API_TOKEN,
    JIRA_IN_PROGRESS_TRANSITION,
    JIRA_READY_FOR_REVIEW_TRANSITION,
    JIRA_SERVER,
)
from glu.gh import get_repo_name_from_repo_config, prompt_for_reviewers
from glu.jira import (
    create_ticket,
    format_jira_ticket,
    generate_ticket_with_ai,
    get_jira_issuetypes,
    get_jira_project,
    get_user_from_jira,
)
from glu.local import (
    checkout_to_branch,
    create_commit,
    get_first_commit_since_checkout,
    get_git_diff,
    get_repo,
    get_repo_name,
    prompt_commit_edit,
    push,
    remote_branch_in_sync,
)
from glu.utils import (
    print_error,
)

app = typer.Typer()


@app.command(short_help="Create a PR with description")
def create(  # noqa: C901
    ticket: Annotated[
        str | None,
        typer.Option("--ticket", "-t", help="Jira ticket number"),
    ] = None,
    project: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Jira project (defaults to default Jira project)"),
    ] = None,
    draft: Annotated[bool, typer.Option("--draft", "-d", help="Mark as draft PR")] = False,
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
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="AI model",
        ),
    ] = None,
):
    try:
        local_repo = get_repo()
        repo_name = get_repo_name(local_repo)
    except InvalidGitRepositoryError as err:
        print_error("Not valid a git repository")
        raise typer.Exit(1) from err

    chat_provider = prompt_for_chat_provider(provider)

    auth = Auth.Token(GITHUB_PAT)
    gh = Github(auth=auth)
    repo = gh.get_repo(repo_name)

    latest_commit: Commit | None = None
    if local_repo.is_dirty():
        commit_choice = inquirer.select(
            "You have uncommitted changes.",
            [
                "Commit and push with AI message",
                "Commit and push with manual message",
                "Proceed anyway",
            ],
        ).execute()
        match commit_choice:
            case "Commit and push with AI message":
                rich.print("[grey70]Generating commit...[/]\n")
                create_commit(local_repo, "chore: [dry run commit]", dry_run=True)
                diff = get_git_diff(local_repo)
                commit_data = prompt_commit_edit(
                    generate_commit_message(
                        chat_provider, model, diff, local_repo.active_branch.name
                    )
                )

                checkout_to_branch(
                    local_repo, repo.default_branch, commit_data.message, chat_provider, model
                )
                latest_commit = create_commit(local_repo, commit_data.message)
                push(local_repo)
            case "Commit and push with manual message":
                create_commit(local_repo, "chore: [dry run commit]", dry_run=True)
                commit_message = typer.edit("")
                if not commit_message:
                    print_error("No commit message provided")
                    raise typer.Exit(0)

                checkout_to_branch(
                    local_repo, repo.default_branch, commit_message, chat_provider, model
                )
                latest_commit = create_commit(local_repo, commit_message)
                push(local_repo)
            case "Proceed anyway":
                checkout_to_branch(local_repo, repo.default_branch, commit_message=None)
            case _:
                print_error("No matching choice for commit was provided")
                raise typer.Exit(1)

    try:
        local_repo.remotes["origin"].fetch(local_repo.active_branch.name, prune=True)
    except GitCommandError:
        push(local_repo)

    if not remote_branch_in_sync(local_repo.active_branch.name, repo=local_repo):
        confirm_push = typer.confirm(
            "Local branch is not up to date with remote. Push to remote now?"
        )
        if confirm_push:
            push(local_repo)

    jira = JIRA(JIRA_SERVER, basic_auth=(EMAIL, JIRA_API_TOKEN))

    first_commit = get_first_commit_since_checkout()
    commit = latest_commit or first_commit

    jira_project = get_jira_project(jira, repo_name, project) if ticket else ""

    title = (
        first_commit.summary.decode()
        if isinstance(first_commit.summary, bytes)
        else first_commit.summary
    )
    body = _create_pr_body(commit, jira_project, ticket)

    selected_reviewers = prompt_for_reviewers(gh, reviewers, repo_name, draft)

    rich.print("[grey70]Generating description...[/]")
    pr_description = generate_description(
        repo, local_repo, body, chat_provider, model, jira_project
    )

    if not ticket:
        ticket_choice = typer.prompt(
            "Ticket [enter #, enter (g) to generate, or Enter to skip]",
            default="",
            show_default=False,
        )
        if ticket_choice.lower() == "g":
            jira_project = jira_project or get_jira_project(jira, repo_name, project)
            rich.print("[grey70]Generating ticket...[/]\n")

            issuetypes = get_jira_issuetypes(jira, jira_project)
            ticket_data = generate_ticket_with_ai(
                repo_name,
                chat_provider,
                model,
                issuetypes=issuetypes,
                pr_description=pr_description,
            )

            myself_ref = get_user_from_jira(jira, user_query=None)

            jira_issue = create_ticket(
                jira,
                jira_project,
                ticket_data.issuetype,
                ticket_data.summary,
                ticket_data.description,
                myself_ref,
                myself_ref,
            )
            ticket = jira_issue.key.split("-")[1]
        elif ticket_choice.isdigit():
            ticket = ticket_choice
            jira_project = jira_project or get_jira_project(jira, repo_name, project)
        else:
            return

    if pr_description and ticket and jira_project:
        pr_description = _add_jira_key_to_description(pr_description, jira_project, ticket)

    pr = repo.create_pull(
        repo.default_branch,
        local_repo.active_branch.name,
        title=title,
        body=pr_description or body or "",
        draft=draft,
    )
    pr.add_to_assignees(gh.get_user().login)

    if selected_reviewers:
        for selected_reviewer in selected_reviewers:
            try:
                pr.create_review_request(selected_reviewer.login)
            except GithubException as e:
                print_error(f"Failed to add reviewer {selected_reviewer.login}: {e}")

    rich.print(f"\n[grey70]{pr_description}[/]\n")
    rich.print(f":rocket: Created PR in [blue]{repo_name}[/] with title [bold green]{title}[/]")
    rich.print(f"[dark violet]https://github.com/{repo_name}/pull/{pr.number}[/]")

    if not ticket:
        return

    ticket_id = format_jira_ticket(jira_project, ticket or "")

    try:
        transitions = [transition["name"] for transition in jira.transitions(ticket_id)]

        if JIRA_IN_PROGRESS_TRANSITION in transitions:
            jira.transition_issue(ticket_id, JIRA_IN_PROGRESS_TRANSITION)
            transitions = [transition["name"] for transition in jira.transitions(ticket_id)]

        if not draft and JIRA_READY_FOR_REVIEW_TRANSITION in transitions:
            jira.transition_issue(ticket_id, JIRA_READY_FOR_REVIEW_TRANSITION)
            rich.print(f":eyes: Moved issue [blue]{ticket_id}[/] to [green]Ready for review[/]")
    except JIRAError as err:
        rich.print(err)
        raise typer.Exit(1) from err


@app.command(short_help="Merge a PR")
def merge(  # noqa: C901
    pr_num: Annotated[int, typer.Option("--pr", help="PR number")],
    repo: Annotated[
        str | None,
        typer.Option("--repo", "-r", help="Github repo", show_default=False),
    ] = None,
    ticket: Annotated[
        str | None,
        typer.Option("--ticket", "-t", help="Jira ticket number", show_default=False),
    ] = None,
    project: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Jira project (defaults to default Jira project)"),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            "-pr",
            help="AI model provider",
            show_default=False,
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="AI model",
            show_default=False,
        ),
    ] = None,
):
    auth = Auth.Token(GITHUB_PAT)
    gh = Github(auth=auth)

    if project:
        jira_project = project
    elif DEFAULT_JIRA_PROJECT:
        project_confirmation = typer.confirm(f"Confirm project is {DEFAULT_JIRA_PROJECT}?")
        if project_confirmation:
            jira_project = DEFAULT_JIRA_PROJECT
        else:
            jira_project = typer.prompt("Enter Jira project name")
    else:
        jira_project = typer.prompt("Enter Jira project name")

    if repo:
        repo_name = repo
    else:
        try:
            local_repo = get_repo()
            repo_name = get_repo_name(local_repo)
        except InvalidGitRepositoryError:
            repo = get_repo_name_from_repo_config(jira_project)
            if not repo:
                repo_name = f"{typer.prompt('Enter org name')}/{typer.prompt('Enter repo name')}"
            else:
                repo_name = repo

    gh_repo = gh.get_repo(repo_name)

    pr = gh_repo.get_pull(pr_num)
    commits = pr.get_commits()

    all_commit_messages = [commit_ref.commit.message for commit_ref in commits]
    summary_commit_message = "\n\n".join(f"* {msg}" for msg in all_commit_messages)

    commit_choice = inquirer.select(
        "You have uncommitted changes.",
        ["Commit with AI message", "Create manual message"],
    ).execute()

    match commit_choice:
        case "Commit with AI message":
            chat_provider = prompt_for_chat_provider(provider, raise_if_no_api_key=True)

            if ticket:
                if not ticket.isdigit():
                    ticket = typer.prompt("Enter ticket number")
                    if not ticket:
                        print_error("No ticket number provided")
                        raise typer.Exit(1)
                formatted_ticket = format_jira_ticket(jira_project, ticket, with_brackets=True)
            else:
                text = f"{summary_commit_message}\n{pr.body}"
                jira_matched = _search_jira_key_in_text(text, jira_project)
                if jira_matched:
                    formatted_ticket = text[jira_matched.pos : jira_matched.endpos]
                else:
                    ticket = typer.prompt("Enter ticket number")
                    if not ticket:
                        print_error("No ticket number provided")
                        raise typer.Exit(1)
                    formatted_ticket = format_jira_ticket(jira_project, ticket, with_brackets=True)

            rich.print("[grey70]Generating commit...[/]\n")

            commit_data = prompt_commit_edit(
                generate_final_commit_message(
                    chat_provider,
                    model,
                    summary_commit_message,
                    pr.body,
                )
            )
            commit_body = f"{commit_data.body}\n\n{formatted_ticket}"
            commit_title = commit_data.full_title
        case "Create manual message":
            commit_msg = typer.edit(summary_commit_message)
            if not commit_msg:
                print_error("No commit message provided")
                raise typer.Exit(0)
            commit_title = commit_msg.split("\n\n")[0]
            commit_body = commit_msg.split("\n\n")[1]
        case _:
            print_error("No matching choice for commit was provided")
            raise typer.Exit(1)

    pr.merge(commit_body, commit_title, merge_method="squash")
    rich.print(f":rocket: Merged PR [bold green]#{pr_num}[/] in [blue]{repo_name}[/]")


def _create_pr_body(commit: Commit, jira_key: str, ticket: str | None) -> str | None:
    commit_message = commit.message if isinstance(commit.message, str) else commit.message.decode()
    try:
        body = (
            commit_message.replace(
                commit.summary if isinstance(commit.summary, str) else commit.summary.decode(),
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


def _search_jira_key_in_text(text: str, jira_project: str) -> re.Match[str] | None:
    """
    Search for any substring matching [{jira_project}-NUMBERS/LETTERS] (e.g. [ABC-XX1234]
    or ABC-XX1234).

    Args:
        text: The input string to search.

    Returns:
        The match, if found.
    """
    pattern = rf"\[?{jira_project}-[A-Za-z0-9]+\]?"

    return re.search(pattern, text)


def _add_jira_key_to_description(text: str, jira_project: str, jira_key: str | int) -> str:
    """
    Search for any substring matching [{jira_project}-NUMBERS/LETTERS] (e.g. [ABC-XX1234]
    or ABC-XX1234) and replace each occurrence with the formatted Jira key.

    Args:
        text: The input string to search.
        jira_key: The Jira key to substitute in place of each [...] match.

    Returns:
        A new string with all [LETTERS-NUMBERS] patterns replaced.
    """
    pattern = rf"\[?{jira_project}-[A-Za-z0-9]+\]?"
    formatted_key = format_jira_ticket(jira_project, jira_key, with_brackets=True)

    if formatted_key in text:
        return text  # already present

    if re.search(pattern, text) is not None:
        return re.sub(pattern, formatted_key, text)

    return f"{text}\n\n{jira_key}"
