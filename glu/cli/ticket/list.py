import rich
import typer
from git import InvalidGitRepositoryError
from rich.table import Column, Table
from rich.text import Text

from glu.jira import get_jira_client, get_jira_project
from glu.local import get_git_client
from glu.utils import abbreviate_last_name, print_error, print_panel, suppress_traceback


@suppress_traceback
def list_tickets(  # noqa: C901
    project: str | None,
    only_mine: bool,
    statuses: list[str] | None,
    order_by_priority: bool,
    priorities: list[str] | None,
    in_progress_only: bool,
    open: bool,
) -> None:
    jira = get_jira_client()
    if not project:
        try:
            git = get_git_client()
            repo_name = git.repo_name
        except InvalidGitRepositoryError as err:
            print_error("Not a valid git repository. Specify Jira project name")
            raise typer.Exit(1) from err

        jira_project = get_jira_project(jira, repo_name, project)
    else:
        jira_project = project

    issue_filters = [f"project={jira_project}"]
    if only_mine:
        issue_filters.append("assignee = currentUser()")

    if statuses:
        issue_filters.append(f"status IN ({','.join(statuses)})")
    else:
        if open:
            issue_filters.append("resolution = unresolved")
        if in_progress_only:
            issue_filters.append('status != "to do"')

    if priorities:
        issue_filters.append(f"priority IN ({','.join(priorities)})")

    order = "priority" if order_by_priority else "created"
    issue_filter = f"{' and '.join(issue_filters)} order by {order} desc"

    issues = jira.search_issues(issue_filter)

    if not issues:
        rich.print("No issues found")

    ticket_table = Table(
        Column(width=2),
        Column("Key", style="deep_sky_blue1"),
        Column("Summary", max_width=100, no_wrap=True),
        Column("Status", no_wrap=True),
        Column("Priority", no_wrap=True),
        Column("Assignee", no_wrap=True, style="light_steel_blue"),
        Column("Reporter", no_wrap=True, style="dark_slate_gray1"),
        box=None,
        padding=(0, 1),
    )

    for issue in issues:
        status_emoji = ""
        if issue.fields.resolution:
            status_emoji = ":white_check_mark:"
        elif issue.fields.status.name.lower() != "to do":
            status_emoji = ":small_blue_diamond:"

        match issue.fields.priority.name.lower():
            case "lowest":
                priority_color = "dodger_blue3"
            case "low":
                priority_color = "dodger_blue1"
            case "high":
                priority_color = "red1"
            case "highest":
                priority_color = "red3"
            case _:
                priority_color = "bright_white"

        match issue.fields.status.name.lower():
            case "to do":
                status_color = "white"
            case _ if issue.fields.resolution:
                status_color = "chartreuse3"
            case _:
                status_color = "bright_white"

        ticket_table.add_row(
            status_emoji,
            issue.key,
            Text(issue.fields.summary, style=status_color),
            Text(issue.fields.status.name, style=status_color),
            Text(issue.fields.priority.name, style=priority_color),
            abbreviate_last_name(
                issue.fields.assignee.displayName if issue.fields.assignee else None
            ),
            abbreviate_last_name(
                issue.fields.reporter.displayName if issue.fields.reporter else None
            ),
        )

    print_panel(title=Text(f"Tickets ({jira_project})"), content=ticket_table)
