import re

import rich
import typer
from git import InvalidGitRepositoryError
from github import GithubException
from InquirerPy import inquirer
from jira import JIRAError

from glu.ai import (
    generate_final_commit_message,
    get_ai_client,
    prompt_for_chat_provider,
)
from glu.config import (
    JIRA_DONE_TRANSITION,
)
from glu.gh import (
    get_all_from_paginated_list,
    get_github_client,
    get_pr_approval_status,
    get_repo_name_from_repo_config,
    print_status_checks,
)
from glu.jira import (
    format_jira_ticket,
    get_jira_client,
    get_jira_project,
)
from glu.local import get_git_client, prompt_commit_edit
from glu.utils import print_error, suppress_traceback


@suppress_traceback
def merge_pr(  # noqa: C901
    pr_num: int,
    ticket: str | None,
    project: str | None,
    provider: str | None,
    model: str | None,
    mark_as_done: bool,
) -> None:
    try:
        git = get_git_client()
        repo_name = git.repo_name
    except InvalidGitRepositoryError:
        repo_name = ""

    jira = get_jira_client()
    jira_project = get_jira_project(jira, repo_name, project)

    if not repo_name:
        repo = get_repo_name_from_repo_config(jira_project) if jira_project else None
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
    pr_checks = gh.get_pr_checks(pr_num)
    for check in pr_checks:
        if check.conclusion == "skipped" or check.status == "waiting":
            continue

        relevant_checks.append(check)
        if check.conclusion != "success" and check.name not in [
            check.name for check in pr_checks if check.conclusion == "success"
        ]:
            bad_checks += 1

    if bad_checks:
        print_status_checks(relevant_checks)
        typer.confirm("Not all status checks passed. Continue?", abort=True)

    commits = get_all_from_paginated_list(pr.get_commits())

    all_commit_messages = [commit_ref.commit.message for commit_ref in commits]
    summary_commit_message = f"{all_commit_messages[0]}\n\n" + "\n\n".join(
        f"* {msg}" for msg in all_commit_messages[1:]
    )

    formatted_ticket: str | None = None
    if jira_project:
        if ticket:
            if not ticket.isdigit():
                ticket = typer.prompt(
                    "Enter ticket number [enter to skip]", default="", show_default=False
                )

            if ticket:
                formatted_ticket = format_jira_ticket(jira_project, ticket, with_brackets=True)
        else:
            text = f"{summary_commit_message}\n{pr.body}"
            jira_matched = _search_jira_key_in_text(text, jira_project)
            if jira_matched:
                formatted_ticket = text[jira_matched.start() : jira_matched.end()]
            else:
                ticket = typer.prompt(
                    "Enter ticket number [enter to skip]", default="", show_default=False
                )
                if ticket:
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
            commit_body = (
                f"{body}\n\n{formatted_ticket}"
                if formatted_ticket and formatted_ticket not in body
                else body
            )
        case _:
            print_error("No matching choice for commit was provided")
            raise typer.Exit(1)

    rich.print("[grey70]Merging PR...[/]\n")
    try:
        pr.merge(
            commit_body,
            commit_title,
            merge_method="squash",
            delete_branch=not gh.delete_branch_on_merge,  # github will handle if True
        )
    except GithubException as err:
        print_error(str(err))
        raise typer.Exit(1) from err

    rich.print(f":rocket: Merged PR [bold green]#{pr_num}[/] in [blue]{repo_name}[/]")

    if mark_as_done and formatted_ticket:
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
