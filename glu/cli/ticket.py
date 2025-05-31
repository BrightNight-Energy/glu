from typing import Annotated, Any

import rich
import typer
from git import InvalidGitRepositoryError
from InquirerPy import inquirer
from jira import JIRA
from typer import Context

from glu.ai import generate_ticket, prompt_for_chat_provider
from glu.config import DEFAULT_JIRA_PROJECT, EMAIL, JIRA_API_TOKEN, JIRA_SERVER
from glu.git import get_repo_name
from glu.jira import get_jira_project, get_user_from_jira
from glu.models import ChatProvider, TicketGeneration
from glu.utils import get_kwargs, print_error, prompt_or_edit

app = typer.Typer()


@app.command(
    short_help="Create a Jira ticket",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def create(
    ctx: Context,
    summary: Annotated[
        str | None,
        typer.Option(
            "--summary",
            "-s",
            "--title",
            help="Issue summary or title",
        ),
    ] = None,
    type: Annotated[str | None, typer.Option("--type", "-t", help="Issue type")] = None,
    body: Annotated[
        str | None,
        typer.Option("--body", "-b", help="Issue description"),
    ] = None,
    assignee: Annotated[str | None, typer.Option("--assignee", "-a", help="Assignee")] = None,
    reporter: Annotated[str | None, typer.Option("--reporter", "-r", help="Reporter")] = None,
    priority: Annotated[str | None, typer.Option("--priority", "-y", help="Priority")] = None,
    project: Annotated[str | None, typer.Option("--project", "-p", help="Jira project")] = None,
    ai_prompt: Annotated[
        str | None,
        typer.Option("--ai-prompt", "-ai", help="AI prompt to generate summary and description"),
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
    extra_fields: dict[str, Any] = get_kwargs(ctx)

    jira = JIRA(JIRA_SERVER, basic_auth=(EMAIL, JIRA_API_TOKEN))

    try:
        repo_name = get_repo_name()
    except InvalidGitRepositoryError:
        repo_name = None

    project = project or DEFAULT_JIRA_PROJECT
    if not project:
        project = get_jira_project(jira, repo_name)

    types = [issuetype.name for issuetype in jira.issue_types_for_project(project or "")]
    if not type:
        issuetype = inquirer.select("Select type:", types).execute()
    else:
        if type.title() not in types:
            issuetype = inquirer.select("Select type:", types).execute()
        else:
            issuetype = type

    if ai_prompt:
        # typer does not currently support union types
        # once they do, the below will work
        # keep an eye on: https://github.com/fastapi/typer/pull/1148
        # if isinstance(ai_prompt, bool):
        #     prompt = prompt_or_edit('AI Prompt')
        # else:
        prompt = ai_prompt

        provider = prompt_for_chat_provider(provider, True)
        ticket_data = _generate_with_ai_prompt(prompt, provider, issuetype, repo_name)
        summary = ticket_data.summary
        body = ticket_data.description
    else:
        if not summary:
            summary = typer.prompt(
                "Summary",
                show_default=False,
            )

        if not body:
            body = prompt_or_edit("Description", allow_skip=True)

    reporter_id = get_user_from_jira(jira, reporter)

    assignee_id = get_user_from_jira(jira, assignee)

    if priority:
        extra_fields["priority"] = priority

    fields = extra_fields | {
        "project": project,
        "issuetype": issuetype,
        "description": body,
        "summary": summary,
        "reporter": reporter_id,
        "assignee": assignee_id,
    }

    issue = jira.create_issue(fields)

    rich.print(f":page_with_curl: Created issue [bold red]{issue.key}[/]")
    rich.print(f"View at {issue.permalink()}")


def _generate_with_ai_prompt(
    ai_prompt: str,
    provider: ChatProvider | None,
    issuetype: str,
    repo_name: str | None,
    requested_changes: str | None = None,
    previous_attempt: TicketGeneration | None = None,
) -> TicketGeneration:
    ticket_data = generate_ticket(
        ai_prompt, issuetype, repo_name, provider, requested_changes, previous_attempt
    )
    summary = ticket_data.summary
    body = ticket_data.description

    rich.print(f"[grey70]Proposed summary:[/]\n{summary}\n")
    rich.print(f"[grey70]Proposed description:[/]\n{body}")

    proceed_choice = inquirer.select(
        "How would you like to proceed?",
        ["Accept", "Edit", "Ask for changes", "Amend prompt and regenerate", "Exit"],
    ).execute()

    match proceed_choice:
        case "Accept":
            return ticket_data
        case "Edit":
            edited = typer.edit(f"Summary: {summary}\n\nDescription: {body}")
            if edited is None:
                print_error("No description provided")
                raise typer.Exit(1)
            summary = edited.split("\n\n")[0].replace("Summary:", "").strip()
            body = edited.split("\n\n")[1].replace("Description:", "").strip()
            return TicketGeneration(description=body, summary=summary)
        case "Ask for changes":
            requested_changes = typer.edit("")
            if requested_changes is None:
                print_error("No changes requested.")
                raise typer.Exit(1)
            return _generate_with_ai_prompt(
                ai_prompt,
                provider,
                issuetype,
                repo_name,
                requested_changes,
                ticket_data,
            )
        case "Amend prompt and regenerate":
            amended_prompt = typer.edit(ai_prompt)
            if amended_prompt is None:
                print_error("No prompt provided.")
                raise typer.Exit(1)
            return _generate_with_ai_prompt(
                amended_prompt,
                provider,
                issuetype,
                repo_name,
            )
        case _:
            raise typer.Exit(0)
