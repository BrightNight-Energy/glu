from git import InvalidGitRepositoryError
from rich.text import Text

from glu.config import DEFAULT_JIRA_PROJECT
from glu.jira import get_color_for_priority, get_color_for_status, get_jira_client, get_jira_project
from glu.local import get_git_client
from glu.utils import print_panel, suppress_traceback


@suppress_traceback
def view_ticket(
    ticket_num: int,
    project: str | None,
) -> None:
    jira = get_jira_client()

    try:
        repo_name = get_git_client().repo_name
    except InvalidGitRepositoryError:
        repo_name = None

    project = project or DEFAULT_JIRA_PROJECT
    if not project:
        jira_project = get_jira_project(jira, repo_name)
    else:
        jira_project = project

    issue = jira.get_issue(jira_project, ticket_num)
    fields = issue.fields

    issue_text = Text("Title:\n", style="grey70")
    issue_text.append(f"{fields.summary}\n\n", style="bright_white")
    if fields.description:
        issue_text.append("Body:\n")
        issue_text.append(f"{fields.description}\n\n", style="bright_white")

    priority_color = get_color_for_priority(fields.priority.name)
    status_color = get_color_for_status(fields.status.name, fields.resolution)
    status_style_kwarg = (
        {"style": f"bright_white on {status_color}"}
        if status_color != "bright_white"
        else {"style": "bright_white"}
    )

    issue_text.append("Status: ")
    issue_text.append(f"{fields.status.name}\n", **status_style_kwarg)
    issue_text.append("Type: ")
    issue_text.append(f"{fields.issuetype.name}\n", style="yellow1")
    issue_text.append("Assignee: ")
    issue_text.append(
        f"{fields.assignee.displayName}\n" if fields.assignee else "[None]",
        style="light_steel_blue",
    )
    issue_text.append("Reporter: ")
    issue_text.append(
        f"{fields.reporter.displayName}\n" if fields.reporter else "[None]",
        style="dark_slate_gray1",
    )
    issue_text.append("Priority: ")
    issue_text.append(f"{fields.priority.name}\n", style=priority_color)

    print_panel(f"{jira_project}-{ticket_num}", issue_text, border_style=status_color)
