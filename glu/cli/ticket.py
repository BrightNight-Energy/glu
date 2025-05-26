from typing import Annotated, Any

import rich
import typer
from InquirerPy import inquirer
from jira import JIRA
from typer import Context

from glu.config import JIRA_SERVER, EMAIL, JIRA_API_TOKEN, DEFAULT_JIRA_PROJECT
from glu.git import get_repo_name
from glu.utils import get_kwargs
from glu.jira import get_user_from_jira, get_jira_project

app = typer.Typer()


@app.command(
    short_help="Create a Jira ticket",
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
)
def create(
    ctx: Context,
    summary: Annotated[
        str,
        typer.Option(
            "--summary", "-s", "--title", help="Issue summary or title", prompt=True
        ),
    ],
    type: Annotated[str | None, typer.Option("--type", "-t", help="Issue type")] = None,
    body: Annotated[
        str | None,
        typer.Option("--body", "-b", help="Issue description"),
    ] = None,
    assignee: Annotated[
        str | None, typer.Option("--assignee", "-a", help="Assignee")
    ] = None,
    reporter: Annotated[
        str | None, typer.Option("--reporter", "-r", help="Reporter")
    ] = None,
    priority: Annotated[
        str | None, typer.Option("--priority", "-y", help="Priority")
    ] = None,
    project: Annotated[
        str | None, typer.Option("--project", "-p", help="Jira project")
    ] = None,
):
    extra_fields: dict[str, Any] = get_kwargs(ctx)

    jira = JIRA(JIRA_SERVER, basic_auth=(EMAIL, JIRA_API_TOKEN))

    project = project or DEFAULT_JIRA_PROJECT
    if not project:
        repo_name = get_repo_name()
        project = get_jira_project(jira, repo_name)

    if not body:
        choice = typer.prompt(
            "Description [(e) to launch editor, enter to skip]",
            default="",
            show_default=False,
        )

        if choice.lower() == "e":
            body = typer.edit("") or ""
        elif choice:
            body = choice

    if not type:
        types = [
            issuetype.name for issuetype in jira.issue_types_for_project(project or "")
        ]
        type = inquirer.select("Select type:", types).execute()

    reporter_id = get_user_from_jira(jira, reporter)

    assignee_id = get_user_from_jira(jira, assignee)

    if priority:
        extra_fields["priority"] = priority

    fields = extra_fields | {
        "project": project,
        "issuetype": type,
        "description": body,
        "summary": summary,
        "reporter": reporter_id,
        "assignee": assignee_id,
    }

    issue = jira.create_issue(fields)

    rich.print(f"Created issue [bold red]{issue.key}[/] :page_with_curl:")
    rich.print(f"View at {issue.permalink()}")
