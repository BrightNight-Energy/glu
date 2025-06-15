from typing import Annotated

import typer

from glu.cli.pr.create import create_pr
from glu.cli.pr.merge import merge_pr

app = typer.Typer()


@app.command(short_help="Create a PR with description")
def create(  # noqa: C901
    ticket: Annotated[
        str | None,
        typer.Option("--ticket", "-t", help="Jira ticket number"),
    ] = None,
    project: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Jira project (defaults to default Jira project)"),
    ] = None,
    draft: Annotated[bool, typer.Option("--draft", "-d", help="Mark as draft PR")] = False,
    reviewers: Annotated[
        list[str] | None,
        typer.Option(
            "--reviewer",
            "-r",
            help="Requested reviewers (accepts multiple values)",
            show_default=False,
        ),
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
    ready_for_review: Annotated[
        bool,
        typer.Option(
            "--review",
            help="Move ticket to ready for review",
        ),
    ] = False,
):
    create_pr(ticket, project, draft, reviewers, provider, model, ready_for_review)


@app.command(short_help="Merge a PR")
def merge(  # noqa: C901
    pr_num: Annotated[int, typer.Argument(help="PR number")],
    ticket: Annotated[
        str | None,
        typer.Option("--ticket", "-t", help="Jira ticket number", show_default=False),
    ] = None,
    project: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Jira project (defaults to default Jira project)"),
    ] = None,
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            "-pr",
            help="AI model provider",
            show_default=False,
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            "-m",
            help="AI model",
            show_default=False,
        ),
    ] = None,
    mark_as_done: Annotated[
        bool,
        typer.Option(
            "--mark-done",
            help="Move Jira ticket to done",
        ),
    ] = False,
):
    merge_pr(pr_num, ticket, project, provider, model, mark_as_done)
