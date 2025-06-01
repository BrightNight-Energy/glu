from typing import Annotated

import rich
import toml
import typer
from InquirerPy import inquirer

from glu import __version__
from glu.cli import pr, ticket
from glu.config import (
    Config,
    EnvConfig,
    JiraIssueTemplateConfig,
    Preferences,
    RepoConfig,
    config_path,
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
    openai_api_key: Annotated[
        str,
        typer.Option(
            help="OpenAI API key",
            hide_input=True,
            prompt=True,
            show_default=False,
            rich_help_panel="OpenAI Config",
        ),
    ],
    openai_org_id: Annotated[
        str,
        typer.Option(
            help="OpenAI organization ID",
            show_default=False,
            prompt=True,
            rich_help_panel="OpenAI Config",
        ),
    ],
    jira_server: Annotated[
        str, typer.Option(help="Jira server URL", prompt=True, rich_help_panel="Jira Config")
    ] = DEFAULTS.jira_server,
    jira_in_progress: Annotated[
        str,
        typer.Option(
            help="Jira 'in progress' transition name", prompt=True, rich_help_panel="Jira Config"
        ),
    ] = DEFAULTS.jira_in_progress_transition,
    jira_ready_for_review: Annotated[
        str,
        typer.Option(
            help="Jira 'ready for review' transition name",
            prompt=True,
            rich_help_panel="Jira Config",
        ),
    ] = DEFAULTS.jira_ready_for_review_transition,
    default_jira_project: Annotated[
        str | None,
        typer.Option(
            help="Default Jira project key",
            show_default=False,
            rich_help_panel="Jira Config",
        ),
    ] = None,
    glean_api_token: Annotated[
        str | None,
        typer.Option(
            help="Glean API token",
            hide_input=True,
            show_default=False,
            rich_help_panel="Glean Config",
        ),
    ] = None,
    glean_instance: Annotated[
        str | None,
        typer.Option(help="Glean instance URL", show_default=False, rich_help_panel="Glean Config"),
    ] = None,
) -> None:
    """
    Initialize the Glu configuration file interactively.
    """
    cfg_path = config_path()
    rich.print(f"[grey70]Config file will be written to {cfg_path}[/]")

    if cfg_path.exists():
        typer.confirm("Config file already exists. Overwrite?", default=False, abort=True)

    env = EnvConfig(
        jira_server=jira_server,
        email=email,
        jira_api_token=jira_api_token,
        jira_in_progress_transition=jira_in_progress,
        jira_ready_for_review_transition=jira_ready_for_review,
        default_jira_project=default_jira_project or None,
        github_pat=github_pat,
        openai_api_key=openai_api_key or None,
        openai_org_id=openai_org_id or None,
        glean_api_token=glean_api_token or None,
        glean_instance=glean_instance or None,
    )

    init_repo_config = typer.confirm(
        "Do you want to initialize repo config?",
        prompt_suffix=" (recommended to setup for ease-of-use):",
    )
    repos: dict[str, RepoConfig] = {}
    if init_repo_config:
        repos = _setup_repos()

    init_issuetemplates = typer.confirm(
        "Do you want to initialize templates for different Jira issue types?"
    )
    jira_config: dict[str, JiraIssueTemplateConfig] = {}
    if init_issuetemplates:
        jira_config = _setup_jira_config()

    preferences = Preferences()
    preferred_provider = inquirer.select(
        "Preferred LLM provider?", ["None (let me pick every time)", "OpenAI", "Glean"]
    ).execute()
    match preferred_provider:
        case "OpenAI":
            preferences.preferred_provider = preferred_provider
            if not env.openai_api_key:
                env.openai_api_key = typer.prompt("OpenAI API Key", hide_input=True)
            if not env.openai_org_id:
                env.openai_org_id = typer.prompt("OpenAI Org ID", default="") or None
        case "Glean":
            preferences.preferred_provider = preferred_provider
            if not env.glean_api_token:
                env.glean_api_token = (
                    typer.prompt("Glean API Token (ask your admin for this key)", default="")
                    or None
                )
            if not env.glean_instance:
                env.glean_instance = typer.prompt("Glean Instance")
        case _:
            preferences.preferred_provider = None

    auto_accept_generated_commits = inquirer.select(
        "Auto accept generated commits?", ["No", "Yes"]
    ).execute()
    preferences.auto_accept_generated_commits = auto_accept_generated_commits == "Yes"

    config = Config(env=env, preferences=preferences, repos=repos, jira_issue=jira_config)

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(toml.dumps(config.export()), encoding="utf-8")

    rich.print(f":white_check_mark: Config file written to {cfg_path}")


def _setup_repos(
    org_name: str | None = None, repos: dict[str, RepoConfig] | None = None
) -> dict[str, RepoConfig]:
    org_name = typer.prompt("Org name", default=org_name)
    repo_name = typer.prompt("Repo name")

    config = RepoConfig()
    config.jira_project_key = typer.prompt("Jira project key")
    add_pr_template = typer.confirm(
        "Add PR template? (If none given, will attempt to pull PR template from repo's "
        ".github folder or fall back to GLU's own default template)",
        default=True,
    )
    if add_pr_template:
        config.pr_template = typer.edit("")

    repo = {f"{org_name}/{repo_name}": config}

    setup_another = typer.confirm("Do you want to setup another repo?")
    if setup_another:
        return _setup_repos(org_name, (repos or {}) | repo)

    return (repos or {}) | repo


def _setup_jira_config(
    templates: dict[str, JiraIssueTemplateConfig] | None = None,
) -> dict[str, JiraIssueTemplateConfig]:
    issuetype = typer.prompt("Issue type? (Generally, 'Bug', 'Story', 'Chore', etc")
    template = typer.edit("Description:\n{description}") or "Description:\n{description}"

    issuetemplate = {issuetype: JiraIssueTemplateConfig(issuetemplate=template)}

    setup_another = typer.confirm("Do you want to setup another issue template?")
    if setup_another:
        return _setup_jira_config((templates or {}) | issuetemplate)

    return (templates or {}) | issuetemplate


app.add_typer(
    pr.app, name="pr", help="Interact with pull requests.", rich_help_panel=":rocket: Commands"
)
app.add_typer(
    ticket.app,
    name="ticket",
    help="Interact with Jira tickets.",
    rich_help_panel=":rocket: Commands",
)


if __name__ == "__main__":
    app()
