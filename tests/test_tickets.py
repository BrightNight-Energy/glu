# ruff: noqa: ARG001, ARG002
import re

import pexpect
from pexpect import spawn

from tests.utils import Key, get_terminal_text


def test_create_ticket_w_base_config(write_base_config, env_cli):
    child = pexpect.spawn("glu ticket create", env=env_cli, encoding="utf-8")

    _create_ticket(child, select_project=True)


def test_create_ticket_w_no_repo_config(write_config_w_repo_config, env_cli):
    child = pexpect.spawn("glu ticket create", env=env_cli, encoding="utf-8")

    _create_ticket(child)


def test_create_ticket_w_ai(write_config_w_repo_config, env_cli):
    child = pexpect.spawn("glu ticket create -ai 'adding testing'", env=env_cli, encoding="utf-8")

    _create_ticket(child, with_ai=True)


def _create_ticket(child: spawn, with_ai: bool = False, select_project: bool = False):
    if select_project:
        child.expect("Select project: ")
        child.send("TEST")
        child.send(Key.DOWN.value)
        child.send(Key.ENTER.value)

    child.expect("Select type:")

    child.expect("Chore")
    plain_menu = get_terminal_text(child.before + child.after)

    assert "Chore" in plain_menu
    assert "Spike" in plain_menu
    assert "Bug" in plain_menu
    assert "Story" in plain_menu

    # Move highlight down twice to select "Story"
    child.send(Key.DOWN.value)
    child.send(Key.DOWN.value)
    child.send(Key.ENTER.value)

    if with_ai:
        child.expect("Select provider:")
        child.send(Key.ENTER.value)  # select first provider
        child.expect("Exit")
        ai_ticket_menu = get_terminal_text(child.before + child.after).strip()

        assert "Proposed ticket body:" in ai_ticket_menu
        assert "- Add tests for main repository commands" in ai_ticket_menu

        assert "Accept" in ai_ticket_menu
        assert "Edit" in ai_ticket_menu
        assert "Amend prompt and regenerate" in ai_ticket_menu
        assert "Exit" in ai_ticket_menu
        child.send(Key.ENTER.value)
    else:
        child.expect("Summary:")
        child.sendline("This is a test")
        child.expect("Description")
        child.sendline("")

    child.expect("📃 Created issue")
    confirmation = child.before + child.after
    assert "Created issue" in confirmation

    child.expect(re.compile(r"View at https?://\S+"))
    text = get_terminal_text(child.before + child.after).strip()
    lines = text.splitlines()
    assert lines[-1].startswith("View at http")
    assert lines[0] in lines[-1]
