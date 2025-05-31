import typer
from InquirerPy import inquirer
from InquirerPy.base import Choice
from jira import JIRA

from glu.config import REPO_CONFIGS
from glu.utils import print_error, filterable_menu


def get_user_from_jira(jira: JIRA, user_query: str | None) -> dict[str, str]:
    myself = jira.myself()
    if not user_query or user_query in ["me@me"]:
        return {"id": myself["accountId"]}

    users = jira.search_users(query=user_query)
    if not len(users):
        print_error(f"No user found with name '{user_query}'")
        raise typer.Exit(1)

    if len(users) == 1:
        return {"id": users[0].accountId}

    choice = inquirer.select(
        "Select reporter:",
        choices=[Choice(user.accountId, user.displayName) for user in users],
    ).execute()

    return {"id": choice}


def get_jira_project(
    jira: JIRA, repo_name: str | None, project: str | None = None
) -> str:
    if REPO_CONFIGS.get(repo_name or "") and REPO_CONFIGS[repo_name or ""].jira_key:
        return REPO_CONFIGS[repo_name or ""].jira_key  # type: ignore

    projects = jira.projects()
    project_keys = [project.key for project in projects]
    if project and project.upper() in [project.key for project in projects]:
        return project.upper()

    selected_project = filterable_menu("Select project: ", project_keys)
    return selected_project


def format_jira_ticket(jira_key: str, ticket: str | int) -> str:
    try:
        ticket_num = int(ticket)
    except ValueError:
        print_error(
            "Jira ticket must be an integer. Provide the Jira project key via the config.toml file"
        )
        raise typer.Exit(1)

    return f"{jira_key}-{ticket_num}"
