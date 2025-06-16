from typing import Annotated

import typer

from glu import __version__
from glu.cli.commit import index as commit
from glu.cli.init import init_config
from glu.cli.pr import index as pr
from glu.cli.ticket import index as ticket
from glu.config import (
    EnvConfig,
)

app = typer.Typer(rich_markup_mode="rich")

DEFAULTS = EnvConfig.defaults()


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


@app.command(rich_help_panel=":hammer_and_wrench: Config")
def init(
    jira_api_token: Annotated[
        str,
        typer.Option(
            help="Jira API token",
            hide_input=True,
            prompt="Jira API token (generate one here: "
            "https://id.atlassian.com/manage-profile/security/api-tokens)",
            show_default=False,
            rich_help_panel="Jira Config",
        ),
    ],
    email: Annotated[
        str,
        typer.Option(
            "--jira-email",
            "--email",
            help="Jira email",
            prompt="Jira email",
            rich_help_panel="Jira Config",
        ),
    ],
    github_pat: Annotated[
        str,
        typer.Option(
            help="GitHub Personal Access Token",
            hide_input=True,
            show_default=False,
            prompt="Github PAT (must be a classic PAT, see here: "
            "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/"
            "managing-your-personal-access-tokens#creating-a-personal-access-token-classic "
            "for more info)",
            rich_help_panel="Github Config",
        ),
    ],
    jira_server: Annotated[
        str, typer.Option(help="Jira server URL", prompt=True, rich_help_panel="Jira Config")
    ] = DEFAULTS.jira_server,
    jira_in_progress: Annotated[
        str,
        typer.Option(
            help="Jira 'in progress' transition name",
            prompt="Jira 'in progress' transition name",
            rich_help_panel="Jira Config",
        ),
    ] = DEFAULTS.jira_in_progress_transition,
    jira_ready_for_review: Annotated[
        str,
        typer.Option(
            help="Jira 'ready for review' transition name",
            prompt="Jira 'ready for review' transition name",
            rich_help_panel="Jira Config",
        ),
    ] = DEFAULTS.jira_ready_for_review_transition,
    jira_done: Annotated[
        str,
        typer.Option(
            help="Jira 'done' transition name",
            prompt="Jira 'done' transition name",
            rich_help_panel="Jira Config",
        ),
    ] = DEFAULTS.jira_done_transition,
    default_jira_project: Annotated[
        str | None,
        typer.Option(
            help="Default Jira project key",
            show_default=False,
            rich_help_panel="Jira Config",
        ),
    ] = None,
    generated_with_glu_tag: Annotated[
        bool,
        typer.Option(
            help="Add a tag to generated PRs and tickets to spread the word about glu!",
            rich_help_panel="Preferences",
            prompt="Add a tag to generated PRs and tickets to spread the word about glu?",
        ),
    ] = True,
) -> None:
    """
    Initialize the Glu configuration file interactively.
    """
    init_config(
        jira_api_token,
        email,
        github_pat,
        jira_server,
        jira_in_progress,
        jira_ready_for_review,
        jira_done,
        default_jira_project,
        generated_with_glu_tag,
    )


app.add_typer(
    pr.app, name="pr", help="Interact with pull requests.", rich_help_panel=":rocket: Commands"
)
app.add_typer(
    ticket.app,
    name="ticket",
    help="Interact with Jira tickets.",
    rich_help_panel=":rocket: Commands",
)

app.add_typer(
    commit.app,
    name="commit",
    help="Interact with commits.",
    rich_help_panel=":rocket: Commands",
)


if __name__ == "__main__":
    app()
