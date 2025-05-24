from pathlib import Path

import typer
from git import Repo

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
    for entry in head_ref.log():  # this walks the reflog
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
