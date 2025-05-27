from pathlib import Path
import os
import toml
from pydantic import BaseModel, ValidationError, Field


class RepoConfig(BaseModel):
    jira_key: str | None = None
    pr_template: str | None = None


class JiraIssueTemplateConfig(BaseModel):
    issuetemplate: str


class EnvConfig(BaseModel):
    jira_server: str
    email: str
    jira_api_token: str
    jira_in_progress_transition: str
    jira_ready_for_review_transition: str
    default_jira_project: str | None = None
    github_pat: str
    openai_api_key: str | None = None
    openai_org_id: str | None = None
    glean_api_token: str | None = None
    glean_instance: str | None = None

    @classmethod
    def defaults(cls) -> "EnvConfig":
        return cls(
            jira_server="https://jira.atlassian.com",
            email="your_jira_email",
            jira_api_token="your_jira_api_token",
            jira_in_progress_transition="Starting",
            jira_ready_for_review_transition="Ready for review",
            github_pat="your_github_pat",
        )


class Config(BaseModel):
    env: EnvConfig
    repos: dict[str, RepoConfig] = Field(default_factory=dict)
    jira_issue_config: dict[str, JiraIssueTemplateConfig] = Field(default_factory=dict)


def config_path() -> Path:
    base = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "glu" / "config.toml"


def ensure_config():
    path = config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

        default_config = {"env": EnvConfig.defaults(), "repos": {}}

        path.write_text(toml.dumps(default_config), encoding="utf-8")


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
JIRA_ISSUE_TEMPLATES = config.jira_issue_config

# jira
JIRA_SERVER = config.env.jira_server
EMAIL = config.env.email
JIRA_API_TOKEN = config.env.jira_api_token
JIRA_IN_PROGRESS_TRANSITION = config.env.jira_in_progress_transition
JIRA_READY_FOR_REVIEW_TRANSITION = config.env.jira_ready_for_review_transition
DEFAULT_JIRA_PROJECT = config.env.default_jira_project

# github
GITHUB_PAT = config.env.github_pat

# glean
if glean_api_token := config.env.glean_api_token:
    os.environ["GLEAN_API_TOKEN"] = glean_api_token
if glean_instance := config.env.glean_instance:
    os.environ["GLEAN_INSTANCE"] = glean_instance

# openai
if openai_api_key := config.env.openai_api_key:
    os.environ["OPENAI_API_KEY"] = openai_api_key
if openai_org_id := config.env.openai_org_id:
    os.environ["OPENAI_ORG_ID"] = openai_org_id
