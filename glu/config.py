import os
from pathlib import Path

import toml
from pydantic import BaseModel, Field, ValidationError, field_validator

from glu.models import ChatProvider

DEFAULT_MODELS: dict[ChatProvider, str] = {
    "OpenAI": "o4-mini",
    "Gemini": "gemini-2.0-flash",
    "Anthropic": "claude-sonnet-4-0",
    "xAI": "grok-3-mini-fast",
    "Ollama": "llama3.2",
}


class RepoConfig(BaseModel):
    jira_project_key: str | None = None
    pr_template: str | None = None


class JiraIssueTemplateConfig(BaseModel):
    issuetemplate: str


class ModelConfig(BaseModel):
    api_key: str
    model: str
    provider: ChatProvider


class OpenAIConfig(ModelConfig):
    org_id: str | None = None
    provider: ChatProvider = Field(default="OpenAI", frozen=True)
    model: str = DEFAULT_MODELS["OpenAI"]


class GleanConfig(ModelConfig):
    model: str = "_"
    provider: ChatProvider = Field(default="Glean", frozen=True)
    instance: str


class GeminiConfig(ModelConfig):
    provider: ChatProvider = Field(default="Gemini", frozen=True)
    model: str = DEFAULT_MODELS["Gemini"]


class AnthropicConfig(ModelConfig):
    provider: ChatProvider = Field(default="Anthropic", frozen=True)
    model: str = DEFAULT_MODELS["Anthropic"]


class XAIConfig(ModelConfig):
    provider: ChatProvider = Field(default="xAI", frozen=True)
    model: str = DEFAULT_MODELS["xAI"]


class OllamaConfig(ModelConfig):
    provider: ChatProvider = Field(default="Ollama", frozen=True)
    model: str = DEFAULT_MODELS["Ollama"]
    api_key: str = "_"


ProviderConfig = (
    OpenAIConfig | GleanConfig | GeminiConfig | AnthropicConfig | XAIConfig | OllamaConfig
)


class EnvConfig(BaseModel):
    jira_server: str
    email: str
    jira_api_token: str
    jira_in_progress_transition: str = "Starting"
    jira_ready_for_review_transition: str = "Ready for review"
    jira_done_transition: str = "Finished"
    default_jira_project: str | None = None
    github_pat: str
    openai_config: OpenAIConfig | None = None
    glean_config: GleanConfig | None = None
    gemini_config: GeminiConfig | None = None
    anthropic_config: AnthropicConfig | None = None
    xai_config: XAIConfig | None = None
    ollama_config: OllamaConfig | None = None

    @classmethod
    def defaults(cls) -> "EnvConfig":
        return cls(
            jira_server="https://jira.atlassian.com",
            email="your_jira_email",
            jira_api_token="your_jira_api_token",
            github_pat="your_github_pat",
        )


class Preferences(BaseModel):
    auto_accept_generated_commits: bool = False
    preferred_provider: ChatProvider | None = None
    add_generated_with_glu_tag: bool = True


class Config(BaseModel):
    env: EnvConfig
    preferences: Preferences = Preferences()
    repos: dict[str, RepoConfig] = Field(default_factory=dict)
    jira_issue: dict[str, JiraIssueTemplateConfig] = Field(default_factory=dict)

    @classmethod
    @field_validator("jira_issue_config")
    def validate_jira_issue_config(
        cls, v: dict[str, JiraIssueTemplateConfig]
    ) -> dict[str, JiraIssueTemplateConfig]:
        return {k.lower(): data for k, data in v.items()}

    def export(self) -> dict:
        base = self.model_dump(exclude_none=True)
        if not self.repos:
            base.pop("repos")
        if not self.jira_issue:
            base.pop("jira_issue")
        return base


def config_path() -> Path:
    if os.getenv("GLU_TEST"):
        from tests import TESTS_DATA_DIR

        return TESTS_DATA_DIR / "config.toml"

    base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "glu" / "config.toml"


def ensure_config():
    path = config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

        default_config = Config(env=EnvConfig.defaults())

        path.write_text(toml.dumps(default_config.model_dump()), encoding="utf-8")


def get_config() -> Config:
    with open(config_path(), "r") as f:
        config = toml.load(f)

    try:
        return Config.model_validate(config)
    except ValidationError as e:
        raise ValueError(f"Error when setting up env variables:\n\n{e}") from e


ensure_config()

config = get_config()

REPO_CONFIGS = config.repos
JIRA_ISSUE_TEMPLATES = config.jira_issue

# jira
JIRA_SERVER = config.env.jira_server
EMAIL = config.env.email
JIRA_API_TOKEN = config.env.jira_api_token
JIRA_IN_PROGRESS_TRANSITION = config.env.jira_in_progress_transition
JIRA_READY_FOR_REVIEW_TRANSITION = config.env.jira_ready_for_review_transition
JIRA_DONE_TRANSITION = config.env.jira_done_transition
DEFAULT_JIRA_PROJECT = config.env.default_jira_project

# github
GITHUB_PAT = config.env.github_pat

# glean
if glean_config := config.env.glean_config:
    os.environ["GLEAN_API_TOKEN"] = glean_config.api_key
    os.environ["GLEAN_INSTANCE"] = glean_config.instance

# openai
if openai_config := config.env.openai_config:
    os.environ["OPENAI_API_KEY"] = openai_config.api_key
    if openai_config.org_id:
        os.environ["OPENAI_ORG_ID"] = openai_config.org_id

DEFAULT_OPENAI_MODEL = (
    config.env.openai_config.model if config.env.openai_config else DEFAULT_MODELS["OpenAI"]
)

# gemini
if gemini_config := config.env.gemini_config:
    os.environ["GOOGLE_API_KEY"] = gemini_config.api_key

DEFAULT_GEMINI_MODEL = (
    config.env.gemini_config.model if config.env.gemini_config else DEFAULT_MODELS["Gemini"]
)

# anthropic
if anthropic_config := config.env.anthropic_config:
    os.environ["ANTHROPIC_API_KEY"] = anthropic_config.api_key

DEFAULT_ANTHROPIC_MODEL = (
    config.env.anthropic_config.model
    if config.env.anthropic_config
    else DEFAULT_MODELS["Anthropic"]
)

# anthropic
if xai_config := config.env.xai_config:
    os.environ["XAI_API_KEY"] = xai_config.api_key

DEFAULT_XAI_MODEL = config.env.xai_config.model if config.env.xai_config else DEFAULT_MODELS["xAI"]

# ollama
DEFAULT_OLLAMA_MODEL = (
    config.env.ollama_config.model if config.env.ollama_config else DEFAULT_MODELS["Ollama"]
)

PREFERENCES = config.preferences

MODEL_TOKEN_LIMITS = {
    # === OpenAI === https://platform.openai.com/docs/models
    "gpt-3.5-turbo": 4096,
    "gpt-3.5-turbo-16k": 16384,
    "gpt-4": 8192,
    "gpt-4-32k": 32768,
    "gpt-4-turbo": 128000,
    "gpt-4o": 128000,
    "o4-mini": 200_000,
    "o3": 200_000,
    "o3-pro": 200_000,
    "o3-mini": 200_000,
    "o1": 200_000,
    "o1-pro": 200_000,
    "gpt-4.1": 1_047_576,
    "gpt-4.1-nano": 1_047_576,
    "gpt-4.1-mini": 1_047_576,
    # === Anthropic (Claude) === https://docs.anthropic.com/en/docs/about-claude/models/overview
    "claude-1": 100000,
    "claude-2": 100000,
    "claude-2.1": 200000,
    "claude-3-haiku-20240307": 200000,
    "claude-3-sonnet-20240229": 200000,
    "claude-3-opus-20240229": 200000,
    "claude-sonnet-4-0": 200_000,
    "claude-opus-4-20250514": 200_000,
    "claude-sonnet-4-20250514": 200_000,
    "claude-3-7-sonnet-20250219": 200_000,
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
    # === Google (Gemini) === https://ai.google.dev/gemini-api/docs/models
    "gemini-pro": 32000,
    "gemini-pro-vision": 32000,
    "gemini-1.5-pro-latest": 1048576,  # 1 million tokens
    "gemini-1.5-flash-latest": 1048576,
    "gemini-2.0-flash": 1_048_576,
    "gemini-2.0-flash-lite": 1_048_576,
    "gemini-2.5-pro": 1_048_576,
    "gemini-2.5-flash": 1_048_576,
    "gemini-2.5-flash-lite-preview-06-17": 1_000_000,
    # === Meta (LLaMA via Ollama, etc.) ===
    "llama-2-7b": 4096,
    "llama-2-13b": 4096,
    "llama-2-70b": 4096,
    "llama3-8b": 8192,
    "llama3-70b": 8192,
    "llama3.2": 8192,
    # === xAI (Grok) === https://docs.x.ai/docs/models
    "grok-3": 131072,
    "grok-3-fast": 131072,
    "grok-3-mini": 131072,
    "grok-3-mini-fast": 131072,
}
