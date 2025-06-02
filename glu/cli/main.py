from typing import Annotated

import rich
import toml
import typer
from InquirerPy import inquirer

from glu import __version__
from glu.cli import pr, ticket
from glu.config import (
    DEFAULT_MODELS,
    AnthropicConfig,
    Config,
    EnvConfig,
    GeminiConfig,
    GleanConfig,
    JiraIssueTemplateConfig,
    OllamaConfig,
    OpenAIConfig,
    Preferences,
    ProviderConfig,
    RepoConfig,
    XAIConfig,
    config_path,
)
from glu.models import CHAT_PROVIDERS, ChatProvider

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
    default_jira_project: Annotated[
        str | None,
        typer.Option(
            help="Default Jira project key",
            show_default=False,
            rich_help_panel="Jira Config",
        ),
    ] = None,
) -> None:
    """
    Initialize the Glu configuration file interactively.
    """
    cfg_path = config_path()
    rich.print(f"[grey70]Config file will be written to {cfg_path}[/]")

    if cfg_path.exists():
        typer.confirm("Config file already exists. Overwrite?", default=False, abort=True)

    provider_configs = _setup_model_providers()

    env = EnvConfig.model_validate(
        provider_configs
        | {
            "jira_server": jira_server,
            "email": email,
            "jira_api_token": jira_api_token,
            "jira_in_progress_transition": jira_in_progress,
            "jira_ready_for_review_transition": jira_ready_for_review,
            "default_jira_project": default_jira_project or None,
            "github_pat": github_pat,
        }
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

    if len(provider_configs) > 1:
        available_providers = [config.provider for config in provider_configs.values()]
        preferred_provider = inquirer.select(
            "Preferred LLM provider?", ["None (let me pick every time)"] + available_providers
        ).execute()
        if preferred_provider == "None (let me pick every time)":
            preferences.preferred_provider = None
        else:
            preferences.preferred_provider = preferred_provider
    elif len(provider_configs) == 1:
        preferences.preferred_provider = list(provider_configs.values())[0].provider

    auto_accept_generated_commits = inquirer.select(
        "Auto accept generated commits?", ["No", "Yes"]
    ).execute()
    preferences.auto_accept_generated_commits = auto_accept_generated_commits == "Yes"

    config = Config(env=env, preferences=preferences, repos=repos, jira_issue=jira_config)

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(toml.dumps(config.export()), encoding="utf-8")

    rich.print(f":white_check_mark: Config file written to {cfg_path}")


def _setup_model_providers(  # noqa: C901
    provider_configs: dict[str, ProviderConfig] | None = None,
    available_providers: list[ChatProvider] | None = None,
) -> dict[str, ProviderConfig]:
    selectable_providers = available_providers or CHAT_PROVIDERS
    provider = inquirer.select("Select provider", selectable_providers + ["Exit"]).execute()

    current_providers = provider_configs or {}
    if provider == "Exit":
        return current_providers

    selectable_providers.remove(provider)

    model = ""  # for typing
    if default_model := DEFAULT_MODELS.get(provider):
        model = typer.prompt(f"{provider} model", default=default_model)

    if provider in ["Ollama"]:
        ollama_config = {"ollama_config": OllamaConfig(model=model)}
        another_provider = (
            typer.confirm("Setup another provider?") if selectable_providers else False
        )
        if another_provider:
            return _setup_model_providers(current_providers | ollama_config, selectable_providers)

        return current_providers | ollama_config

    api_key = typer.prompt(f"{provider} API Key", hide_input=True)

    new_config: dict[str, ProviderConfig] = {}
    match provider:
        case "Glean":
            instance = typer.prompt("Glean Instance")
            new_config = {
                "glean_config": GleanConfig(model=model, api_key=api_key, instance=instance)
            }
        case "OpenAI":
            org_id = typer.prompt("OpenAI Org ID (optional)", default="", show_default=False)
            new_config = {
                "openai_config": OpenAIConfig(model=model, api_key=api_key, org_id=org_id or None)
            }
        case "Gemini":
            new_config = {"gemini_config": GeminiConfig(model=model, api_key=api_key)}
        case "Anthropic":
            new_config = {"anthropic_config": AnthropicConfig(model=model, api_key=api_key)}
        case "xAI":
            new_config = {"xai_config": XAIConfig(model=model, api_key=api_key)}
        case _:
            pass

    another_provider = typer.confirm("Setup another provider?") if selectable_providers else False
    if another_provider:
        return _setup_model_providers(current_providers | new_config, selectable_providers)

    return current_providers | new_config


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
