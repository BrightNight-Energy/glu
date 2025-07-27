import rich
import typer
from git import InvalidGitRepositoryError
from rich.table import Column, Table
from rich.text import Text

from glu.jira import get_color_for_priority, get_color_for_status, get_jira_client, get_jira_project
from glu.local import get_git_client
from glu.utils import abbreviate_last_name, print_error, print_panel, suppress_traceback


@suppress_traceback
def list_tickets(  # noqa: C901
    project: str | None,
    search: str | None,
    only_mine: bool,
    statuses: list[str] | None,
    order_by_priority: bool,
    priorities: list[str] | None,
    types: list[str] | None,
    assignee: str | None,
    reporter: str | None,
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
    elif assignee:
        issue_filters.append(f'assignee="{assignee}"')

    if reporter:
        issue_filters.append(f'reporter="{reporter}"')

    if statuses:
        issue_filters.append(f"status IN ({','.join(statuses)})")
    else:
        if open:
            issue_filters.append("resolution = unresolved")
        if in_progress_only:
            issue_filters.append('status != "to do"')

    if types:
        issue_filters.append(f"issuetype IN ({','.join(types)})")

    if priorities:
        issue_filters.append(f"priority IN ({','.join(priorities)})")

    if search:
        issue_filters.append(f'text ~ "{search}"')

    order = "priority" if order_by_priority else "created"
    issue_filter = f"{' and '.join(issue_filters)} order by {order} desc"

    issues = jira.search_issues(issue_filter)

    if not issues:
        rich.print("No issues found")
        return

    ticket_table = Table(
        Column(width=2),
        Column("Key", style="deep_sky_blue1"),
        Column("Summary", max_width=100, no_wrap=True),
        Column("Type", no_wrap=True, style="yellow1"),
        Column("Status", no_wrap=True),
        Column("Priority", no_wrap=True),
        Column("Assignee", no_wrap=True, style="light_steel_blue"),
        Column("Reporter", no_wrap=True, style="dark_slate_gray1"),
        box=None,
        padding=(0, 1),
    )

    for issue in issues:
        fields = issue.fields
        status_emoji = ""
        if fields.resolution:
            status_emoji = ":white_check_mark:"
        elif fields.status.name.lower() != "to do":
            status_emoji = ":small_blue_diamond:"

        priority_color = get_color_for_priority(fields.priority.name)
        status_color = get_color_for_status(fields.status.name, fields.resolution)

        ticket_table.add_row(
            status_emoji,
            issue.key,
            Text(fields.summary, style=status_color),
            Text(fields.issuetype.name),
            Text(fields.status.name, style=status_color),
            Text(fields.priority.name, style=priority_color),
            abbreviate_last_name(fields.assignee.displayName if fields.assignee else None),
            abbreviate_last_name(fields.reporter.displayName if fields.reporter else None),
        )

    print_panel(title=Text(f"Tickets ({jira_project})"), content=ticket_table)
