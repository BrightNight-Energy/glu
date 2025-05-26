from pathlib import Path

import typer
from git import Repo, GitCommandError

from glu.utils import print_error


def get_repo_name() -> str:
    repo = get_repo()

    if not len(repo.remotes):
        print_error("No remote found for git config")
        raise typer.Exit(1)

    return repo.remotes.origin.url.split(":")[1].replace(".git", "")


def get_repo() -> Repo:
    # get remote repo by parsing .git/config
    cwd = Path.cwd()
    return Repo(cwd, search_parent_directories=True)


def get_first_commit_since_checkout(repo: Repo | None = None):
    """
    Return the first commit made on the current branch since it was last checked out.
    If no new commits have been made, returns None.
    """
    repo = repo or get_repo()
    head_ref = repo.head  # Reference object for HEAD

    # 1) Find the SHA that HEAD pointed to immediately after the last checkout
    checkout_sha = None
    for entry in reversed(head_ref.log()):  # this walks the reflog
        # reflog messages look like: "checkout: moving from main to feature/foo"
        if entry.message.startswith("checkout: moving from"):
            checkout_sha = entry.newhexsha
            break

    if checkout_sha is None:
        print_error("Could not find a commit on this branch")
        raise typer.Exit(1)

    # 2) List all commits exclusive of that checkout point up to current HEAD
    rev_range = f"{checkout_sha}..{head_ref.commit.hexsha}"
    commits = list(repo.iter_commits(rev_range))

    if not commits:
        print_error("Could not find a commit on this branch")
        raise typer.Exit(1)

    # 3) iter_commits returns newest→oldest, so the last item is the _first_ commit
    return commits[-1]


def remote_branch_in_sync(
    branch_name: str, remote_name: str = "origin", repo: Repo | None = None
) -> bool:
    """
    Returns True if:
      - remote_name/branch_name exists, and
      - its commit SHA == the local branch’s commit SHA.
    Returns False otherwise (including if the remote branch doesn’t exist).
    """
    repo = repo or get_repo()

    # 1) Make sure we have up-to-date remote refs
    try:
        repo.remotes[remote_name].fetch(branch_name, prune=True)
    except GitCommandError:
        # fetch failed (e.g. no such remote)
        return False

    # 2) Does the remote branch exist?
    remote_ref_name = f"{remote_name}/{branch_name}"
    refs = [ref.name for ref in repo.refs]
    if remote_ref_name not in refs:
        return False

    # 3) Compare SHAs
    local_sha = repo.heads[branch_name].commit.hexsha
    remote_sha = repo.refs[remote_ref_name].commit.hexsha

    return local_sha == remote_sha
