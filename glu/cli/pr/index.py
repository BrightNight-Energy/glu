from typing import Annotated

import typer

from glu.cli.pr.create import create_pr
from glu.cli.pr.list import list_prs as list_prs_core
from glu.cli.pr.merge import merge_pr
from glu.cli.pr.open import open_pr as open_pr_core
from glu.cli.pr.update import update_pr
from glu.cli.pr.view import view_pr as view_pr_core

app = typer.Typer()


@app.command(short_help="Create a PR with description")
def create(
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
def merge(
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


@app.command(name="list", short_help="List PRs")
def list_prs(
    repo_name: Annotated[
        str | None,
        typer.Option(
            "--repo",
            "-r",
            help="Repo name (defaults to current directory git repository)",
            show_default=False,
        ),
    ] = None,
    only_mine: Annotated[
        bool, typer.Option("--only-mine", "-m", help="Filter PRs to those assigned to me")
    ] = False,
    no_draft: Annotated[
        bool, typer.Option("--no-draft", "-d", help="Filter PRs to exclude draft")
    ] = False,
):
    list_prs_core(repo_name, only_mine, no_draft)


@app.command(name="open", short_help="Open PR in web browser")
def open_pr(
    pr_num: Annotated[int, typer.Argument(help="PR number")],
    repo_name: Annotated[
        str | None,
        typer.Option(
            "--repo",
            "-r",
            help="Repo name (defaults to current directory git repository)",
            show_default=False,
        ),
    ] = None,
):
    open_pr_core(pr_num, repo_name)


@app.command(short_help="View PR")
def view(
    pr_num: Annotated[int, typer.Argument(help="PR number")],
    repo_name: Annotated[
        str | None,
        typer.Option(
            "--repo",
            "-r",
            help="Repo name (defaults to current directory git repository)",
            show_default=False,
        ),
    ] = None,
    show_checks: Annotated[
        bool,
        typer.Option(
            "--checks",
            "--show-checks",
            "-c",
            help="Show CI checks (not enabled by default for performance reasons)",
        ),
    ] = False,
):
    view_pr_core(pr_num, repo_name, show_checks)


@app.command(short_help="Update a PR with description")
def update(
    pr_num: Annotated[int, typer.Argument(help="PR number")],
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
    update_pr(pr_num, ticket, project, draft, reviewers, provider, model, ready_for_review)
