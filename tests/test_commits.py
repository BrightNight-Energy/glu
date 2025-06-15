# ruff: noqa: ARG001, ARG002
import pexpect

from tests.utils import get_terminal_text


def test_list_commits(env_cli, write_config_w_repo_config):
    child = pexpect.spawn("glu commit list", env=env_cli, encoding="utf-8")

    child.expect("╰─────")

    table = get_terminal_text(child.before + child.after)

    assert "fix: modularize command structure and add error suppression" in table
    assert "chore(release): v2.1.0" in table
    assert "fix: Detect and inject jira ticket placeholder in pr desc" in table


def test_count_commits(env_cli, write_config_w_repo_config):
    child = pexpect.spawn("glu commit count", env=env_cli, encoding="utf-8")

    child.expect("Commits since main: 5")
