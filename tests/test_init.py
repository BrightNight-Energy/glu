import os

import pexpect

from tests import TESTS_DATA_DIR
from tests.utils import Key, get_terminal_text


def test_init(env_cli):
    if (TESTS_DATA_DIR / "config.toml").exists():
        os.remove(TESTS_DATA_DIR / "config.toml")

    child = pexpect.spawn("glu init", env=env_cli, encoding="utf-8")

    child.expect("Jira API token")
    jira_api_token = "dfj3kjf9dfj3"
    child.send(f"{jira_api_token}{Key.ENTER.value}")
    child.expect("Jira email:")
    jira_email = "email@me.com"
    child.send(f"{jira_email}{Key.ENTER.value}")
    child.expect("Github PAT")
    github_pat = "dfj2k39f04"
    child.send(f"{github_pat}{Key.ENTER.value}")
    child.expect("Jira server")
    child.send(Key.ENTER.value)  # accept default
    child.expect("Jira 'in progress' transition name")
    child.send(Key.ENTER.value)  # accept default
    child.expect("Jira 'ready for review' transition name")
    child.send(Key.ENTER.value)  # accept default

    child.expect("Exit")

    text = get_terminal_text(child.before + child.after)
    assert "Config file will be written to" in text
    assert "glu/tests/data/config.toml" in text

    assert "Select provider" in text
    assert "OpenAI" in text
    assert "Glean" in text
    assert "Gemini" in text
    assert "Anthropic" in text
    assert "xAI" in text
    assert "Ollama" in text

    child.send(Key.ENTER.value)  # add openAI
    child.expect("OpenAI model")
    child.send(Key.ENTER.value)  # accept default
    child.expect("OpenAI API Key")
    openai_api_key = "adf23hggj9400h"
    child.send(f"{openai_api_key}{Key.ENTER.value}")
    child.expect("OpenAI Org ID")
    child.send(Key.ENTER.value)  # skip
    child.expect("Setup another provider?")
    child.send(f"n{Key.ENTER.value}")  # skip setting up another

    child.expect("Do you want to initialize repo config?")
    child.send(f"y{Key.ENTER.value}")
    child.expect("Org name?")
    org_name = "github"
    child.send(f"{org_name}{Key.ENTER.value}")
    child.expect("Repo name?")
    repo_name = "Test-Repo"
    child.send(f"{repo_name}{Key.ENTER.value}")
    child.expect("Jira project key:")
    child.send(f"TEST{Key.ENTER.value}")
    child.expect("Add PR template?")
    child.send(f"n{Key.ENTER.value}")
    child.expect("Do you want to setup another repo?")
    child.send(f"n{Key.ENTER.value}")

    child.expect("Do you want to initialize templates for different Jira issue types?")
    child.send(f"y{Key.ENTER.value}")
    child.expect("Issue type?")
    child.send(f"Bug{Key.ENTER.value}")
    child.sendline(":wq")  # exit out of vim, accept default
    child.expect("Do you want to setup another issue template?")
    child.send(f"n{Key.ENTER.value}")

    child.expect("Yes")
    auto_accept_generated_commits_menu = get_terminal_text(child.before + child.after)
    assert "Auto accept generated commits?" in auto_accept_generated_commits_menu
    assert "No" in auto_accept_generated_commits_menu
    assert "Yes" in auto_accept_generated_commits_menu
    child.send(Key.ENTER.value)

    child.expect("✅ Config file written to")
