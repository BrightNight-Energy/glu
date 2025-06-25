import os
from typing import Literal

import rich
import typer
from InquirerPy import inquirer
from InquirerPy.base import Choice
from jira import JIRA, Issue, Project

from glu.ai import ChatClient, generate_ticket
from glu.config import EMAIL, JIRA_API_TOKEN, JIRA_SERVER, REPO_CONFIGS
from glu.models import IdReference, JiraUser, TicketGeneration
from glu.utils import filterable_menu, print_error


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
