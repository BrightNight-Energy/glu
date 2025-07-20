import os
import re
from typing import Literal

import typer
from InquirerPy import inquirer
from InquirerPy.base import Choice
from jira import JIRA, Issue, Project
from jira.resources import Resolution
from rich.text import Text

from glu.ai import ChatClient, generate_ticket
from glu.config import EMAIL, JIRA_API_TOKEN, JIRA_SERVER, REPO_CONFIGS
from glu.models import TICKET_PLACEHOLDER, IdReference, JiraUser, TicketGeneration
from glu.utils import filterable_menu, print_error, print_panel


class JiraClient:
    def __init__(self):
        self._client = JIRA(JIRA_SERVER, basic_auth=(EMAIL, JIRA_API_TOKEN))

    def myself(self) -> JiraUser:
        myself = self._client.myself()
        return JiraUser(myself["accountId"], myself["displayName"])

    def projects(self) -> list[Project]:
        return self._client.projects()

    def search_users(self, query: str) -> list[JiraUser]:
        return self._client.search_issues(query)

    def get_issuetypes(self, project: str) -> list[str]:
        return [issuetype.name for issuetype in self._client.issue_types_for_project(project)]

    def get_transitions(self, ticket_id: str) -> list[str]:
        return [transition["name"] for transition in self._client.transitions(ticket_id)]

    def transition_issue(self, ticket_id: str, transition: str) -> None:
        self._client.transition_issue(ticket_id, transition)

    def create_ticket(
        self,
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

        return self._client.create_issue(fields)

    def search_issues(self, jql: str) -> list[Issue]:
        return self._client.search_issues(jql)

    def get_issue(self, project: str, ticket_num: int) -> Issue:
        return self._client.issue(f"{project}-{ticket_num}")


def get_jira_client() -> JiraClient:
    if os.getenv("GLU_TEST"):
        from tests.clients.jira import FakeJiraClient

        return FakeJiraClient()  # type: ignore
    return JiraClient()


def get_user_from_jira(
    jira: JiraClient, user_query: str | None, user_type: Literal["reporter", "assignee"]
) -> IdReference:
    myself = jira.myself()
    if not user_query or user_query in ["me", "@me"]:
        return IdReference(id=myself.accountId)

    users = jira.search_users(query=user_query)
    if not len(users):
        print_error(f"No user found with name '{user_query}'")
        raise typer.Exit(1)

    if len(users) == 1:
        return IdReference(id=users[0].accountId)

    choice = inquirer.select(
        f"Select {user_type}:",
        choices=[Choice(user.accountId, user.displayName) for user in users],
    ).execute()

    return IdReference(id=choice)


def get_jira_project(jira: JiraClient, repo_name: str | None, project: str | None = None) -> str:
    if REPO_CONFIGS.get(repo_name or "") and REPO_CONFIGS[repo_name or ""].jira_project_key:
        return REPO_CONFIGS[repo_name or ""].jira_project_key  # type: ignore

    projects = jira.projects()
    project_keys = [project.key for project in projects]
    if project and project.upper() in [project.key for project in projects]:
        return project.upper()

    return filterable_menu("Select project: ", project_keys)


def format_jira_ticket(jira_key: str, ticket: str | int, with_brackets: bool = False) -> str:
    try:
        ticket_num = int(ticket)
    except ValueError as err:
        print_error("Jira ticket must be an integer.")
        raise typer.Exit(1) from err

    base_key = f"{jira_key}-{ticket_num}"
    return f"[{base_key}]" if with_brackets else base_key


def generate_ticket_with_ai(
    chat_client: ChatClient,
    repo_name: str | None,
    issuetype: str | None = None,
    issuetypes: list[str] | None = None,
    ai_prompt: str | None = None,
    pr_description: str | None = None,
    requested_changes: str | None = None,
    previous_attempt: TicketGeneration | None = None,
) -> TicketGeneration:
    ticket_data = generate_ticket(
        chat_client,
        repo_name,
        issuetype,
        issuetypes,
        ai_prompt,
        pr_description,
        requested_changes,
        previous_attempt,
    )
    summary = ticket_data.summary
    body = ticket_data.description

    print_panel(
        title="Proposed ticket",
        content=Text.from_markup(f"[grey70]Title:[/]\n{summary}\n\n[grey70]Body:[/]\n{body}"),
    )

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
            edited = typer.edit(f"Summary: {summary}\n\nBody:\n{body}")
            if edited is None:
                print_error("No description provided")
                raise typer.Exit(1)
            summary = edited.split("\n\n")[0].replace("Summary:", "").strip()
            try:
                body = edited.split("\n\n")[1].replace("Body:\n", "").strip()
            except IndexError:
                body = ""
            return TicketGeneration(
                description=body, summary=summary, issuetype=ticket_data.issuetype
            )
        case "Ask for changes":
            requested_changes = typer.edit("")
            if requested_changes is None:
                print_error("No changes requested.")
                raise typer.Exit(1)
            return generate_ticket_with_ai(
                chat_client,
                repo_name,
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
                chat_client,
                repo_name,
                issuetype,
                issuetypes,
                amended_prompt,
                pr_description,
                requested_changes,
                ticket_data,
            )
        case _:
            raise typer.Exit(0)


def get_color_for_priority(priority: str) -> str:
    match priority.lower():
        case "lowest":
            return "dodger_blue3"
        case "low":
            return "dodger_blue1"
        case "high":
            return "red1"
        case "highest":
            return "red3"
        case _:
            return "bright_white"


def get_color_for_status(status: str, resolution: Resolution | None) -> str:
    match status.lower():
        case "to do":
            return "white"
        case _ if resolution:
            return "chartreuse3"
        case _:
            return "bright_white"


def add_jira_key_to_pr_description(text: str, formatted_ticket: str) -> str:
    """
    Replace the placeholder Jira ticket with the formatted Jira key.

    Args:
        text: The input string to search.
        formatted_ticket: The Jira key to substitute in place of each [...] match.

    Returns:
        A new string with all [LETTERS-NUMBERS] patterns replaced.
    """

    if formatted_ticket in text:
        return text  # already present

    if TICKET_PLACEHOLDER in text:
        return text.replace(TICKET_PLACEHOLDER, formatted_ticket)

    return f"{text}\n\n{formatted_ticket}"


def search_and_prompt_for_jira_ticket(
    jira_project: str | None, ticket: str | None, text: str
) -> str | None:
    if not jira_project:
        return None

    if ticket:
        if not ticket.isdigit():
            ticket = typer.prompt(
                "Enter ticket number [enter to skip]", default="", show_default=False
            )

        if ticket:
            return format_jira_ticket(jira_project, ticket, with_brackets=True)

    jira_matched = _search_jira_key_in_text(text, jira_project)
    if jira_matched:
        return text[jira_matched.start() : jira_matched.end()]

    ticket = typer.prompt("Enter ticket number [enter to skip]", default="", show_default=False)
    if ticket:
        return format_jira_ticket(jira_project, ticket, with_brackets=True)

    return None


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
