from unittest.mock import MagicMock

from glu.local import GitClient


def test_push_sets_upstream_when_no_tracking():
    client, _, git = _make_client(branch_name="push-test", has_tracking=False)

    client.push()

    git.push.assert_called_once_with("--set-upstream", "origin", "push-test")


def test_push_without_upstream_flag_when_tracking_set():
    client, _, git = _make_client(branch_name="push-test", has_tracking=True)

    client.push()

    git.push.assert_called_once_with("origin", "push-test")


def _make_client(branch_name: str, has_tracking: bool):
    # GitClient() already returns the fake client in tests, but this is scoped narrowly.
    # Client has a _repo attribute
    client = object.__new__(GitClient)

    # _repo has a git attribute and an active branch attribute
    repo = MagicMock()
    git = MagicMock()
    active_branch = MagicMock()

    # Assign mock attributes
    client._repo = repo
    repo.git = git
    repo.active_branch = active_branch

    # Active branch has a name attribute and a tracking_branch method
    active_branch.name = branch_name
    active_branch.tracking_branch.return_value = MagicMock() if has_tracking else None

    return client, repo, git
