# ruff: noqa: ARG002, E501, C901
import os

import pytest
import toml

from glu.config import Config, EnvConfig, RepoConfig
from tests import TESTS_DATA_DIR


@pytest.fixture
def write_base_config():
    default_config = Config(env=EnvConfig.defaults())
    path = TESTS_DATA_DIR / "config.toml"
    path.write_text(toml.dumps(default_config.model_dump()), encoding="utf-8")


@pytest.fixture
def write_config_w_repo_config():
    default_config = Config(
        env=EnvConfig.defaults(),
        repos={"github/Test-Repo": RepoConfig(jira_project_key="TEST")},
    )
    path = TESTS_DATA_DIR / "config.toml"
    path.write_text(toml.dumps(default_config.model_dump()), encoding="utf-8")


@pytest.fixture
def env_cli():
    env = os.environ.copy()
    env["TERM"] = "dumb"
    env["GLU_TEST"] = "1"
    env["VISUAL"] = "vim"
    return env
