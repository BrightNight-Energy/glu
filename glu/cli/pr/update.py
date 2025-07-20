import rich
import typer
from git import InvalidGitRepositoryError
from jira import JIRAError

from glu.ai import (
    generate_description,
    get_ai_client,
    prompt_for_chat_provider,
)
from glu.config import JIRA_IN_PROGRESS_TRANSITION, JIRA_READY_FOR_REVIEW_TRANSITION, PREFERENCES
from glu.gh import get_github_client, prompt_for_reviewers
from glu.jira import (
    add_jira_key_to_pr_description,
    format_jira_ticket,
    get_jira_client,
    get_jira_project,
    search_and_prompt_for_jira_ticket,
)
from glu.local import get_git_client
from glu.utils import add_generated_with_glu_tag, print_error, suppress_traceback


@suppress_traceback
def update_pr(
    number: int,
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
        print_error("Not valid a git repository")
        raise typer.Exit(1) from err

    chat_client = get_ai_client(model)
    chat_provider = prompt_for_chat_provider(chat_client, provider)
    chat_client.set_chat_model(chat_provider)

    gh = get_github_client(git.repo_name)

    pr = gh.get_pr(number)

    jira = get_jira_client()

    jira_project = get_jira_project(jira, git.repo_name, project)

    selected_reviewers = prompt_for_reviewers(
        gh, reviewers, git.repo_name, draft or bool(pr.requested_reviewers)
    )

    pr_template = gh.get_contents(".github/pull_request_template.md")
    pr_diff = gh.get_pr_diff(number)
    rich.print("[grey70]Generating description...[/]")
    pr_gen = generate_description(
        chat_client, pr_template, git.repo_name, pr_diff, pr.body, generate_title=True
    )

    formatted_ticket = search_and_prompt_for_jira_ticket(jira_project, ticket, text=pr.body)

    pr_description = pr_gen.description
    if formatted_ticket:
        pr_description = add_jira_key_to_pr_description(pr_description, formatted_ticket)
    if PREFERENCES.add_generated_with_glu_tag:
        pr_description = add_generated_with_glu_tag(pr_description)

    gh.update_pr(
        pr,
        pr_gen.title,
        body=pr_description,
        draft=draft,
    )

    if selected_reviewers:
        gh.add_reviewers_to_pr(pr, selected_reviewers)

    rich.print(f"\n[grey70]{pr_description}[/]\n")
    rich.print(
        f":page_facing_up: Updated PR in [blue]{git.repo_name}[/] "
        f"with title [bold green]'{pr_gen.title}'[/]"
    )
    rich.print(f"[dark violet]https://github.com/{git.repo_name}/pull/{number}[/]")

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
