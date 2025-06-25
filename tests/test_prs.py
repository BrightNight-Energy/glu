# ruff: noqa: ARG001, ARG002
import re
from typing import Literal

import pexpect

from tests.utils import Key, get_terminal_text


def test_create_pr_full_flow_w_ai(write_config_w_repo_config, env_cli):
    env_cli["IS_GIT_DIRTY"] = "1"
    env_cli["IS_JIRA_TICKET_IN_TO_DO"] = "1"
    child = pexpect.spawn("glu pr create", env=env_cli, encoding="utf-8")

    _create_pr(child, is_git_dirty=True)


def test_create_pr_w_no_ticket(write_config_w_repo_config, env_cli):
    env_cli["IS_GIT_DIRTY"] = "1"
    env_cli["IS_JIRA_TICKET_IN_TO_DO"] = "1"
    child = pexpect.spawn("glu pr create", env=env_cli, encoding="utf-8")

    _create_pr(child, is_git_dirty=True, ticket_generation="skip")


def test_merge_pr(env_cli, write_config_w_repo_config):
    child = pexpect.spawn("glu pr merge 263", env=env_cli, encoding="utf-8")

    _merge_pr(child)


def test_merge_draft_pr(env_cli, write_config_w_repo_config):
    env_cli["IS_DRAFT_PR"] = "1"
    child = pexpect.spawn("glu pr merge 263", env=env_cli, encoding="utf-8")

    child.expect("This PR is in draft mode. Would you like to mark it ready for review?")
    child.send(f"y{Key.ENTER.value}")


def test_merge_merged_pr(env_cli, write_config_w_repo_config):
    env_cli["IS_PR_MERGED"] = "1"
    child = pexpect.spawn("glu pr merge 263", env=env_cli, encoding="utf-8")

    child.expect("PR #263 in github/Test-Repo is already merged")


def test_merge_pr_w_conflicts(env_cli, write_config_w_repo_config):
    env_cli["PR_NOT_MERGEABLE"] = "1"
    child = pexpect.spawn("glu pr merge 263", env=env_cli, encoding="utf-8")

    child.expect("PR #263 in github/Test-Repo is not mergeable due to conflicts")


def test_merge_pr_w_failing_cicd(env_cli, write_config_w_repo_config):
    env_cli["IS_CICD_FAILING"] = "1"
    child = pexpect.spawn("glu pr merge 263", env=env_cli, encoding="utf-8")

    child.expect("Not all status checks passed. Continue?")

    status_checks = get_terminal_text(child.before + child.after)

    assert "Deploy to test" not in status_checks
    assert "✅  Validate PR title" in status_checks
    assert "✅  Run tests (3.13)" in status_checks
    assert "✅  Run tests (3.12)" in status_checks
    assert "✅  Run tests (3.11)" in status_checks
    assert "❌  Run tests (3.10)" in status_checks


def test_merge_pr_w_no_ticket(env_cli, write_config_w_repo_config):
    env_cli["PR_HAS_NO_TICKET"] = "1"
    child = pexpect.spawn("glu pr merge 263", env=env_cli, encoding="utf-8")

    _merge_pr(child, no_ticket=True)


def _create_pr(
    child: pexpect.spawn,
    is_git_dirty: bool = False,
    ticket_generation: Literal["ai", "skip"] = "ai",
):
    child.expect("Select provider:")
    child.send(Key.ENTER.value)  # select first provider

    if is_git_dirty:
        child.expect("Proceed anyway")

        text = get_terminal_text(child.before + child.after)
        assert "You have uncommitted changes" in text
        assert "Commit and push with AI message" in text
        assert "Commit and push with manual message" in text
        assert "Proceed anyway" in text

        child.send(Key.ENTER.value)  # ai message

        child.expect("Exit")

        proposed_commit_text = get_terminal_text(child.before + child.after)
        assert "Proposed commit:" in proposed_commit_text
        assert "refactor: Unify client abstractions" in proposed_commit_text
        assert "How would you like to proceed?" in proposed_commit_text
        assert "Accept" in proposed_commit_text
        assert "Edit" in proposed_commit_text
        assert "Exit" in proposed_commit_text

        child.send(Key.ENTER.value)  # accept

    child.expect("Select reviewers:")
    child.send(f"jack{Key.ENTER.value}")
    child.expect("Select reviewers:")
    child.send(Key.ENTER.value)  # end reviewer selection

    child.expect("Ticket")
    text = get_terminal_text(child.before + child.after)
    assert "Generating description..." in text

    if ticket_generation == "ai":
        child.send(f"g{Key.ENTER.value}")  # generate ticket

        child.expect("Generating ticket...")

        child.expect("Exit")
        proposed_ticket_text = get_terminal_text(child.before + child.after)
        assert "Proposed ticket title:" in proposed_ticket_text
        assert "Proposed ticket body:" in proposed_ticket_text
        assert "How would you like to proceed?" in proposed_ticket_text
        assert "Accept" in proposed_ticket_text
        assert "Edit" in proposed_ticket_text
        assert "Ask for changes" in proposed_ticket_text
        assert "Add prompt and regenerate" in proposed_ticket_text
        assert "Exit" in proposed_ticket_text

        child.send(Key.ENTER.value)  # accept
    else:
        child.send(Key.ENTER.value)

    child.expect(re.compile(r"https://github\.com/github/Test-Repo/pull/\d+"))
    text = get_terminal_text(child.before + child.after).strip()

    assert "### Description" in text

    if ticket_generation != "skip":
        assert re.search(r"- \*\*Jira Ticket\*\*: \[TEST-\d+]", text)

    lines = text.splitlines()

    assert lines[-4] == "Generated with (https://github.com/BrightNight-Energy/glu)"
    assert (
        lines[-2] == "🚀 Created PR in github/Test-Repo with title feat: Add testing to my CLI app"
    )
    assert "https://github.com/github/Test-Repo/pull/" in lines[-1]


def _merge_pr(child: pexpect.spawn, no_ticket: bool = False):
    if no_ticket:
        child.expect("Enter ticket number")
        child.send(Key.ENTER.value)

    child.expect("Create manually")
    create_commit_menu = get_terminal_text(child.before + child.after)
    assert "Create commit message." in create_commit_menu
    assert "Create with AI" in create_commit_menu
    assert "Create manually" in create_commit_menu

    child.send(Key.ENTER.value)  # create with AI

    child.expect("Select provider:")
    child.send(Key.ENTER.value)  # select first provider

    child.expect("Exit")
    proposed_commit_text = get_terminal_text(child.before + child.after)
    assert "Proposed commit:" in proposed_commit_text
    assert (
        "fix: Detect and inject jira ticket placeholder in pr descriptions" in proposed_commit_text
    )
    if not no_ticket:
        assert "[TEST-20]" in proposed_commit_text
    assert "How would you like to proceed?" in proposed_commit_text
    assert "Accept" in proposed_commit_text
    assert "Edit" in proposed_commit_text

    child.send(Key.ENTER.value)  # accept

    child.expect("🚀 Merged PR #263 in github/Test-Repo")
    confirmation_text = get_terminal_text(child.before + child.after)
    assert "Merging PR..." in confirmation_text
