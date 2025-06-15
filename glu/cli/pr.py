import re
from typing import Annotated

import rich
import typer
from git import Commit, InvalidGitRepositoryError
from github import GithubException
from InquirerPy import inquirer
from jira import JIRAError

from glu.ai import (
    generate_commit_message,
    generate_description,
    generate_final_commit_message,
    get_ai_client,
    prompt_for_chat_provider,
)
from glu.config import (
    DEFAULT_JIRA_PROJECT,
    JIRA_DONE_TRANSITION,
    JIRA_IN_PROGRESS_TRANSITION,
    JIRA_READY_FOR_REVIEW_TRANSITION,
)
from glu.gh import (
    get_all_from_paginated_list,
    get_github_client,
    get_pr_approval_status,
    get_repo_name_from_repo_config,
    print_status_checks,
    prompt_for_reviewers,
)
from glu.jira import (
    format_jira_ticket,
    generate_ticket_with_ai,
    get_jira_client,
    get_jira_project,
    get_user_from_jira,
)
from glu.local import (
    checkout_to_branch,
    get_git_client,
    prompt_commit_edit,
)
from glu.models import TICKET_PLACEHOLDER
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
    ready_for_review: Annotated[
        bool,
        typer.Option(
            "--review",
            help="Move ticket to ready for review",
        ),
    ] = False,
):
    try:
        git = get_git_client()
    except InvalidGitRepositoryError as err:
        print_error("Not valid a git repository")
        raise typer.Exit(1) from err

    chat_client = get_ai_client(model)
    chat_provider = prompt_for_chat_provider(chat_client, provider)
    chat_client.set_chat_model(chat_provider)

    gh = get_github_client(git.repo_name)

    latest_commit: Commit | None = None
    if git.is_dirty:
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
                git.create_commit("chore: [dry run commit]", dry_run=True)
                rich.print("[grey70]Generating commit...[/]\n")
                diff = git.get_diff()
                commit_data = prompt_commit_edit(
                    generate_commit_message(chat_client, diff, git.current_branch)
                )

                checkout_to_branch(git, chat_client, gh.default_branch, commit_data.message)
                latest_commit = git.create_commit(commit_data.message)
                git.push()
            case "Commit and push with manual message":
                git.create_commit("chore: [dry run commit]", dry_run=True)
                commit_message = typer.edit("")
                if not commit_message:
                    print_error("No commit message provided")
                    raise typer.Exit(0)

                checkout_to_branch(git, chat_client, gh.default_branch, commit_message)
                latest_commit = git.create_commit(commit_message)
                git.push()
            case "Proceed anyway":
                checkout_to_branch(git, chat_client, gh.default_branch, commit_message=None)
            case _:
                print_error("No matching choice for commit was provided")
                raise typer.Exit(1)

    if not git.confirm_branch_exists_in_remote():
        git.push()

    if not git.remote_branch_in_sync():
        confirm_push = typer.confirm(
            "Local branch is not up to date with remote. Push to remote now?"
        )
        if confirm_push:
            git.push()

    jira = get_jira_client()

    first_commit = git.get_first_commit_since_checkout()
    commit = latest_commit or first_commit

    jira_project = get_jira_project(jira, git.repo_name, project) if ticket else ""

    title = (
        first_commit.summary.decode()
        if isinstance(first_commit.summary, bytes)
        else first_commit.summary
    )
    body = _create_pr_body(commit, jira_project, ticket)

    selected_reviewers = prompt_for_reviewers(gh, reviewers, git.repo_name, draft)

    pr_template = gh.get_contents(".github/pull_request_template.md")
    diff_to_main = git.get_diff("main", gh.default_branch)
    rich.print("[grey70]Generating description...[/]")
    pr_description = generate_description(
        chat_client, pr_template, git.repo_name, diff_to_main, body
    )

    if not ticket:
        ticket_choice = typer.prompt(
            "Ticket [enter #, enter (g) to generate, or Enter to skip]",
            default="",
            show_default=False,
        )
        if ticket_choice.lower() == "g":
            jira_project = jira_project or get_jira_project(jira, git.repo_name, project)
            rich.print("[grey70]Generating ticket...[/]\n")

            issuetypes = jira.get_issuetypes(jira_project)
            ticket_data = generate_ticket_with_ai(
                chat_client,
                git.repo_name,
                issuetypes=issuetypes,
                pr_description=pr_description,
            )

            myself_ref = get_user_from_jira(jira, user_query=None, user_type="reporter")

            jira_issue = jira.create_ticket(
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
            jira_project = jira_project or get_jira_project(jira, git.repo_name, project)
        else:
            pass

    if pr_description and ticket and jira_project:
        pr_description = _add_jira_key_to_description(pr_description, jira_project, ticket)

    pr = gh.create_pr(
        git.current_branch,
        title=title,
        body=pr_description or body or "",
        draft=draft,
    )

    if selected_reviewers:
        gh.add_reviewers_to_pr(pr, selected_reviewers)

    rich.print(f"\n[grey70]{pr_description}[/]\n")
    rich.print(f":rocket: Created PR in [blue]{git.repo_name}[/] with title [bold green]{title}[/]")
    rich.print(f"[dark violet]https://github.com/{git.repo_name}/pull/{pr.number}[/]")

    if not ticket:
        return

    ticket_id = format_jira_ticket(jira_project, ticket or "")

    try:
        transitions = jira.get_transitions(ticket_id)

        if JIRA_IN_PROGRESS_TRANSITION in transitions:
            jira.transition_issue(ticket_id, JIRA_IN_PROGRESS_TRANSITION)
            transitions = jira.get_transitions(ticket_id)

        if ready_for_review and not draft and JIRA_READY_FOR_REVIEW_TRANSITION in transitions:
            jira.transition_issue(ticket_id, JIRA_READY_FOR_REVIEW_TRANSITION)
            rich.print(f":eyes: Moved ticket [blue]{ticket_id}[/] to [green]Ready for review[/]")
    except JIRAError as err:
        rich.print(err)
        raise typer.Exit(1) from err


@app.command(short_help="Merge a PR")
def merge(  # noqa: C901
    pr_num: Annotated[int, typer.Argument(help="PR number")],
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
    mark_as_done: Annotated[
        bool,
        typer.Option(
            "--mark-done",
            help="Move Jira ticket to done",
        ),
    ] = False,
):
    try:
        git = get_git_client()
        repo_name = git.repo_name
    except InvalidGitRepositoryError:
        repo_name = ""

    jira = get_jira_client()
    jira_project = get_jira_project(jira, repo_name, project) if repo_name else ""

    if not jira_project:
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

    if not repo_name:
        repo = get_repo_name_from_repo_config(jira_project)
        if not repo:
            repo_name = f"{typer.prompt('Enter org name')}/{typer.prompt('Enter repo name')}"
        else:
            repo_name = repo

    gh = get_github_client(repo_name)

    pr = gh.get_pr(pr_num)

    if pr.draft:
        ready_for_review_confirm = typer.confirm(
            "This PR is in draft mode. Would you like to mark it ready for review?"
        )
        if ready_for_review_confirm:
            pr.mark_ready_for_review()
        raise typer.Exit(0)

    if pr.merged:
        rich.print(f"PR [bold green]#{pr_num}[/] in [blue]{repo_name}[/] is already merged")
        raise typer.Exit(0)

    if not pr.mergeable:
        message = f"PR [bold green]#{pr_num}[/] in [blue]{repo_name}[/] is not mergeable"
        if pr.mergeable_state == "dirty":
            message += " [red]due to conflicts[/]"
        else:
            message += f" [red]({pr.mergeable_state})[/]"
        rich.print(message)
        raise typer.Exit(1)

    pr_approval_status = get_pr_approval_status(pr.get_reviews())
    if pr_approval_status == "changes_requested":
        rich.print(f"PR [bold green]#{pr_num}[/] in [blue]{repo_name}[/] has changes requested")
        raise typer.Exit(1)
    elif pr_approval_status != "approved":
        rich.print(f"PR [bold green]#{pr_num}[/] in [blue]{repo_name}[/] is [red]not approved[/].")
        typer.confirm("Would you like to try to continue anyway?", abort=True)

    relevant_checks = []
    bad_checks = 0
    for check in gh.get_pr_checks(pr_num):
        if check.conclusion == "skipped":
            continue

        relevant_checks.append(check)
        if check.conclusion != "success":
            bad_checks += 1

    if bad_checks:
        print_status_checks(relevant_checks)
        typer.confirm("Not all status checks passed. Continue?", abort=True)

    commits = get_all_from_paginated_list(pr.get_commits())

    all_commit_messages = [commit_ref.commit.message for commit_ref in commits]
    summary_commit_message = f"{all_commit_messages[0]}\n\n" + "\n\n".join(
        f"* {msg}" for msg in all_commit_messages[1:]
    )

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
            formatted_ticket = text[jira_matched.start() : jira_matched.end()]
        else:
            ticket = typer.prompt("Enter ticket number")
            if not ticket:
                print_error("No ticket number provided")
                raise typer.Exit(1)
            formatted_ticket = format_jira_ticket(jira_project, ticket, with_brackets=True)

    commit_choice = inquirer.select(
        "Create commit message.",
        ["Create with AI", "Create manually"],
    ).execute()

    match commit_choice:
        case "Create with AI":
            chat_client = get_ai_client(model)
            chat_provider = prompt_for_chat_provider(
                chat_client, provider, raise_if_no_api_key=True
            )
            chat_client.set_chat_model(chat_provider)

            rich.print("[grey70]Generating commit...[/]\n")

            commit_data = prompt_commit_edit(
                generate_final_commit_message(
                    chat_client,
                    summary_commit_message,
                    formatted_ticket,
                    pr_description=f"{pr.title}\n\n{pr.body}",
                )
            )
            commit_body = f"{commit_data.body}\n\n{formatted_ticket}"
            commit_title = commit_data.full_title
        case "Create manually":
            commit_msg = typer.edit(summary_commit_message)
            if not commit_msg:
                print_error("No commit message provided")
                raise typer.Exit(0)
            commit_title = commit_msg.split("\n\n")[0]
            body = commit_msg.replace(f"{commit_title}\n\n", "", 1).strip()
            commit_body = f"{body}\n\n{formatted_ticket}" if formatted_ticket not in body else body
        case _:
            print_error("No matching choice for commit was provided")
            raise typer.Exit(1)

    rich.print("[grey70]Merging PR...[/]\n")
    try:
        pr.merge(commit_body, commit_title, merge_method="squash", delete_branch=True)
    except GithubException as err:
        print_error(str(err))
        raise typer.Exit(1) from err

    rich.print(f":rocket: Merged PR [bold green]#{pr_num}[/] in [blue]{repo_name}[/]")

    if mark_as_done:
        ticket_id = formatted_ticket[1:-1]  # remove brackets
        try:
            transitions = jira.get_transitions(ticket_id)

            if JIRA_DONE_TRANSITION in transitions:
                jira.transition_issue(ticket_id, JIRA_DONE_TRANSITION)
                rich.print(
                    f":white_check_mark: Marked ticket [blue]{ticket_id}[/] as [green]Done[/]"
                )
        except JIRAError as err:
            rich.print(err)
            raise typer.Exit(1) from err


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
    Replace the placeholder Jira ticket with the formatted Jira key.

    Args:
        text: The input string to search.
        jira_key: The Jira key to substitute in place of each [...] match.

    Returns:
        A new string with all [LETTERS-NUMBERS] patterns replaced.
    """

    formatted_key = format_jira_ticket(jira_project, jira_key, with_brackets=True)

    if formatted_key in text:
        return text  # already present

    if TICKET_PLACEHOLDER in text:
        return text.replace(TICKET_PLACEHOLDER, formatted_key)

    return f"{text}\n\n{formatted_key}"
