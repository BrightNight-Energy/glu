import typer

from glu import __version__
from glu.cli import pr, ticket

app = typer.Typer()


def version_callback(value: bool):
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the version and exit",
    ),
):
    if ctx.invoked_subcommand is None and not version:
        typer.echo(ctx.get_help())


app.add_typer(pr.app, name="pr", help="Interact with pull requests.")
app.add_typer(ticket.app, name="ticket", help="Interact with Jira tickets.")

if __name__ == "__main__":
    app()
