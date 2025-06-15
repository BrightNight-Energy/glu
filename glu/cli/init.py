import rich
import toml
import typer
from InquirerPy import inquirer

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
from glu.utils import suppress_traceback

DEFAULTS = EnvConfig.defaults()


@suppress_traceback
def init_config(
    jira_api_token: str,
    email: str,
    github_pat: str,
    jira_server: str,
    jira_in_progress: str,
    jira_ready_for_review: str,
    jira_done: str,
    default_jira_project: str | None,
    generated_with_glu_tag: bool,
) -> None:
    cfg_path = config_path()
    rich.print(f"[grey70]Config file will be written to {cfg_path}[/]")

    if cfg_path.exists() and "your_github_pat" not in cfg_path.read_text():
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
            "jira_done_transition": jira_done,
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

    preferences.add_generated_with_glu_tag = generated_with_glu_tag

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
    issuetype = typer.prompt("Issue type? (Generally, 'Bug', 'Story', 'Chore', etc)")
    template = typer.edit("Description:\n{description}") or "Description:\n{description}"

    issuetemplate = {issuetype: JiraIssueTemplateConfig(issuetemplate=template)}

    setup_another = typer.confirm("Do you want to setup another issue template?")
    if setup_another:
        return _setup_jira_config((templates or {}) | issuetemplate)

    return (templates or {}) | issuetemplate
