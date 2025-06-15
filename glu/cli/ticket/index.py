from typing import Annotated, Any

import typer
from typer import Context

from glu.cli.ticket.create import create_ticket
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
