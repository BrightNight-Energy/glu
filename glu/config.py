from pathlib import Path
import os
import toml
from pydantic import BaseModel, ValidationError


class RepoConfig(BaseModel):
    JIRA_KEY: str


class EnvConfig(BaseModel):
    JIRA_SERVER: str
    EMAIL: str
    JIRA_API_TOKEN: str
    JIRA_IN_PROGRESS_TRANSITION: str
    JIRA_READY_FOR_REVIEW_TRANSITION: str
    DEFAULT_JIRA_PROJECT: str | None = None
    GITHUB_PAT: str
    GLEAN_API_TOKEN: str
    GLEAN_INSTANCE: str

    @classmethod
    def defaults(cls) -> "EnvConfig":
        return cls(
            JIRA_SERVER="https://jira.atlassian.com",
            EMAIL="your_jira_email",
            JIRA_API_TOKEN="your_jira_api_token",
            JIRA_IN_PROGRESS_TRANSITION="Starting",
            JIRA_READY_FOR_REVIEW_TRANSITION="Ready for review",
            GITHUB_PAT="your_github_pat",
            GLEAN_API_TOKEN="your_glean_api_token",
            GLEAN_INSTANCE="your_glean_instance",
        )


class Config(BaseModel):
    env: EnvConfig
    repos: dict[str, RepoConfig]


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

# jira
JIRA_SERVER = config.env.JIRA_SERVER
EMAIL = config.env.EMAIL
JIRA_API_TOKEN = config.env.JIRA_API_TOKEN
JIRA_IN_PROGRESS_TRANSITION = config.env.JIRA_IN_PROGRESS_TRANSITION
JIRA_READY_FOR_REVIEW_TRANSITION = config.env.JIRA_READY_FOR_REVIEW_TRANSITION
DEFAULT_JIRA_PROJECT = config.env.DEFAULT_JIRA_PROJECT

# github
GITHUB_PAT = config.env.GITHUB_PAT

# glean
os.environ["GLEAN_API_TOKEN"] = config.env.GLEAN_API_TOKEN
os.environ["GLEAN_INSTANCE"] = config.env.GLEAN_INSTANCE
