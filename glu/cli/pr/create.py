import rich
import typer
from git import Commit, InvalidGitRepositoryError
from InquirerPy import inquirer
from jira import JIRAError
from rich.markdown import Markdown

from glu.ai import (
    generate_commit_message,
    generate_description,
    get_ai_client,
    prompt_for_chat_provider,
)
from glu.config import JIRA_IN_PROGRESS_TRANSITION, JIRA_READY_FOR_REVIEW_TRANSITION, PREFERENCES
from glu.gh import get_github_client, prompt_for_reviewers
from glu.jira import (
    add_jira_key_to_pr_description,
    format_jira_ticket,
    generate_ticket_with_ai,
    get_jira_client,
    get_jira_project,
    get_user_from_jira,
)
from glu.local import checkout_to_branch, get_git_client, prompt_commit_edit
from glu.utils import add_generated_with_glu_tag, print_error, suppress_traceback


@suppress_traceback
def create_pr(  # noqa: C901
    ticket: str | None,
    project: str | None,
    draft: bool,
    reviewers: list[str] | None,
    provider: str | None,
    model: str | None,
    ready_for_review: bool,
) -> None:
    try:
        git = get_git_client()
    except InvalidGitRepositoryError as err:
        print_error("Not a valid git repository")
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

    first_commit = git.get_first_commit_since_checkout(gh.default_branch)
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
    pr_gen = generate_description(chat_client, pr_template, git.repo_name, diff_to_main, body)

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
                pr_description=pr_gen.description,
            )

            myself_ref = get_user_from_jira(jira, user_query=None, user_type="reporter")

            ticket_description = ticket_data.description
            if PREFERENCES.add_generated_with_glu_tag:
                ticket_description = add_generated_with_glu_tag(
                    ticket_description, supports_markdown=False
                )

            jira_issue = jira.create_ticket(
                jira_project,
                ticket_data.issuetype,
                ticket_data.summary,
                ticket_description,
                myself_ref,
                myself_ref,
            )
            ticket = jira_issue.key.split("-")[1]
        elif ticket_choice.isdigit():
            ticket = ticket_choice
            jira_project = jira_project or get_jira_project(jira, git.repo_name, project)
        else:
            pass

    pr_description = pr_gen.description
    if ticket and jira_project:
        formatted_ticket = format_jira_ticket(jira_project, ticket, with_brackets=True)
        pr_description = add_jira_key_to_pr_description(pr_description, formatted_ticket)
    if PREFERENCES.add_generated_with_glu_tag:
        pr_description = add_generated_with_glu_tag(pr_description)

    pr = gh.create_pr(
        git.current_branch,
        title=title,
        body=pr_description,
        draft=draft,
    )

    if selected_reviewers:
        gh.add_reviewers_to_pr(pr, selected_reviewers)

    rich.print(Markdown(f"## {title}", style="grey70"))
    rich.print(Markdown(pr_description or "", style="grey70"))
    rich.print(
        f":page_with_curl: Created PR in [blue]{git.repo_name}[/] "
        f"with title [bold green]'{title}'[/]"
    )
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


def _create_pr_body(commit: Commit, jira_key: str, ticket: str | None) -> str | None:
    body = commit.message if isinstance(commit.message, str) else commit.message.decode()

    if not ticket:
        return body

    ticket_str = format_jira_ticket(jira_key, ticket)
    if not body:
        return f"[{ticket_str}]"

    if ticket_str in body:
        return body

    return body.replace(ticket, f"[{ticket_str}]")
