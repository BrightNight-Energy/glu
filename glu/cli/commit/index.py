from typing import Annotated

import typer

from glu.cli.commit.count import count_commits
from glu.cli.commit.list import list_commits

app = typer.Typer()


@app.command(short_help="List commits")
def list(
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            "-l",
            help="Limit number of commits (defaults to number of commits since main)",
            show_default=False,
        ),
    ] = None,
):
    list_commits(limit)


@app.command(short_help="Count commits")
def count(
    branch: Annotated[
        str | None,
        typer.Option(
            "--branch",
            "-b",
            help="Branch to count from (defaults to default branch)",
            show_default=False,
        ),
    ] = None,
):
    count_commits(branch)
