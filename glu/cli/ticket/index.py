from typing import Annotated, Any

import typer
from typer import Context

from glu.cli.ticket.create import create_ticket
from glu.cli.ticket.list import list_tickets as list_tickets_core
from glu.cli.ticket.open import open_ticket as open_ticket_core
from glu.cli.ticket.view import view_ticket
from glu.utils import get_kwargs

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
    issue_type: Annotated[str | None, typer.Option("--type", "-t", help="Issue type")] = None,
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
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="AI model",
        ),
    ] = None,
):
    extra_fields: dict[str, Any] = get_kwargs(ctx)

    create_ticket(
        summary,
        issue_type,
        body,
        assignee,
        reporter,
        priority,
        project,
        ai_prompt,
        provider,
        model,
        **extra_fields,
    )


@app.command(name="list", short_help="List Jira tickets")
def list_tickets(
    project: Annotated[str | None, typer.Option("--project", "-p", help="Jira project")] = None,
    search: Annotated[
        str | None,
        typer.Option("--search", "-q", help="Filter by text", show_default=False),
    ] = None,
    only_mine: Annotated[
        bool,
        typer.Option("--only-mine", "-m", help="Only show my tickets"),
    ] = False,
    statuses: Annotated[
        list[str] | None,
        typer.Option(
            "--status",
            "-s",
            help="Filter tickets by status (multiple values accepted)",
            show_default=False,
        ),
    ] = None,
    order_by_priority: Annotated[
        bool,
        typer.Option(
            "--priority-ordered",
            help="Order by priority (defaults to created date)",
            show_default=False,
        ),
    ] = False,
    show_closed: Annotated[
        bool,
        typer.Option(
            "--show-closed",
            "-c",
            help="Show closed tickets",
        ),
    ] = False,
    priorities: Annotated[
        list[str] | None,
        typer.Option(
            "--priority",
            "-y",
            help="Filter tickets by priority (multiple values accepted)",
            show_default=False,
        ),
    ] = None,
    types: Annotated[
        list[str] | None,
        typer.Option(
            "--type",
            "-t",
            help="Filter tickets by issue type (multiple values accepted)",
            show_default=False,
        ),
    ] = None,
    assignee: Annotated[
        str | None,
        typer.Option(
            "--assignee",
            "-a",
            help="Filter by assignee",
            show_default=False,
        ),
    ] = None,
    reporter: Annotated[
        str | None,
        typer.Option(
            "--reporter",
            "-r",
            help="Filter by reporter",
            show_default=False,
        ),
    ] = None,
    in_progress_only: Annotated[
        bool,
        typer.Option(
            "--in-progress",
            "-i",
            help="Show in progress tickets only",
        ),
    ] = False,
):
    list_tickets_core(
        project,
        search,
        only_mine,
        statuses,
        order_by_priority,
        priorities,
        types,
        assignee,
        reporter,
        in_progress_only,
        open=not show_closed,
    )


@app.command(name="open", short_help="Open Jira ticket in web browser")
def open_ticket(
    ticket_num: Annotated[int, typer.Argument(help="Ticket number")],
    project: Annotated[str | None, typer.Option("--project", "-p", help="Jira project")] = None,
):
    open_ticket_core(ticket_num, project)


@app.command(short_help="View Jira ticket")
def view(
    ticket_num: Annotated[int, typer.Argument(help="Ticket number")],
    project: Annotated[str | None, typer.Option("--project", "-p", help="Jira project")] = None,
):
    view_ticket(ticket_num, project)
