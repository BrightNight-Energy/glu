import rich
import typer
from InquirerPy import inquirer
from InquirerPy.base import Choice
from jira import JIRA, Issue

from glu.ai import generate_ticket
from glu.config import REPO_CONFIGS
from glu.models import ChatProvider, IdReference, TicketGeneration
from glu.utils import filterable_menu, print_error


def get_user_from_jira(jira: JIRA, user_query: str | None) -> IdReference:
    myself = jira.myself()
    if not user_query or user_query in ["me", "@me"]:
        return IdReference(id=myself["accountId"])

    users = jira.search_users(query=user_query)
    if not len(users):
        print_error(f"No user found with name '{user_query}'")
        raise typer.Exit(1)

    if len(users) == 1:
        return IdReference(id=users[0].accountId)

    choice = inquirer.select(
        "Select reporter:",
        choices=[Choice(user.accountId, user.displayName) for user in users],
    ).execute()

    return IdReference(id=choice)


def get_jira_project(jira: JIRA, repo_name: str | None, project: str | None = None) -> str:
    if REPO_CONFIGS.get(repo_name or "") and REPO_CONFIGS[repo_name or ""].jira_project_key:
        return REPO_CONFIGS[repo_name or ""].jira_project_key  # type: ignore

    projects = jira.projects()
    project_keys = [project.key for project in projects]
    if project and project.upper() in [project.key for project in projects]:
        return project.upper()

    return filterable_menu("Select project: ", project_keys)


def get_jira_issuetypes(jira: JIRA, project: str) -> list[str]:
    return [issuetype.name for issuetype in jira.issue_types_for_project(project)]


def format_jira_ticket(jira_key: str, ticket: str | int, with_brackets: bool = False) -> str:
    try:
        ticket_num = int(ticket)
    except ValueError as err:
        print_error("Jira ticket must be an integer.")
        raise typer.Exit(1) from err

    base_key = f"{jira_key}-{ticket_num}"
    return f"[{base_key}]" if with_brackets else base_key


def generate_ticket_with_ai(
    repo_name: str | None,
    chat_provider: ChatProvider | None,
    issuetype: str | None = None,
    issuetypes: list[str] | None = None,
    ai_prompt: str | None = None,
    pr_description: str | None = None,
    requested_changes: str | None = None,
    previous_attempt: TicketGeneration | None = None,
) -> TicketGeneration:
    ticket_data = generate_ticket(
        repo_name,
        chat_provider,
        issuetype,
        issuetypes,
        ai_prompt,
        pr_description,
        requested_changes,
        previous_attempt,
    )
    summary = ticket_data.summary
    body = ticket_data.description

    rich.print(f"[grey70]Proposed ticket title:[/]\n{summary}\n")
    rich.print(f"[grey70]Proposed ticket body:[/]\n{body}")

    choices = [
        "Accept",
        "Edit",
        "Ask for changes",
        f"{'Amend' if ai_prompt else 'Add'} prompt and regenerate",
        "Exit",
    ]

    proceed_choice = inquirer.select(
        "How would you like to proceed?",
        choices,
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
            return TicketGeneration(
                description=body, summary=summary, issuetype=ticket_data.issuetype
            )
        case "Ask for changes":
            requested_changes = typer.edit("")
            if requested_changes is None:
                print_error("No changes requested.")
                raise typer.Exit(1)
            return generate_ticket_with_ai(
                repo_name,
                chat_provider,
                issuetype,
                issuetypes,
                ai_prompt,
                pr_description,
                requested_changes,
                ticket_data,
            )
        case s if s.endswith("prompt and regenerate"):
            amended_prompt = typer.edit(ai_prompt or "")
            if amended_prompt is None:
                print_error("No prompt provided.")
                raise typer.Exit(1)
            return generate_ticket_with_ai(
                repo_name,
                chat_provider,
                issuetype,
                issuetypes,
                amended_prompt,
                pr_description,
                requested_changes,
                ticket_data,
            )
        case _:
            raise typer.Exit(0)


def create_ticket(
    jira: JIRA,
    project: str,
    issuetype: str,
    summary: str,
    description: str | None,
    reporter_ref: IdReference,
    assignee_ref: IdReference,
    **extra_fields: dict,
) -> Issue:
    fields = extra_fields | {
        "project": project,
        "issuetype": issuetype,
        "description": description,
        "summary": summary,
        "reporter": reporter_ref.model_dump(),
        "assignee": assignee_ref.model_dump(),
    }

    return jira.create_issue(fields)
