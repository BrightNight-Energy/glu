from pathlib import Path

import rich
import typer
from git import Commit, GitCommandError, HookExecutionError, Repo
from InquirerPy import inquirer

from glu.ai import generate_commit_message
from glu.config import PREFERENCES
from glu.models import ChatProvider, CommitGeneration
from glu.utils import print_error


def get_repo_name(repo: Repo | None = None) -> str:
    repo = repo or get_repo()

    if not len(repo.remotes):
        print_error("No remote found for git config")
        raise typer.Exit(1)

    return repo.remotes.origin.url.split(":")[1].replace(".git", "")


def get_repo() -> Repo:
    # get remote repo by parsing .git/config
    cwd = Path.cwd()
    return Repo(cwd, search_parent_directories=True)


def get_first_commit_since_checkout(repo: Repo | None = None) -> Commit:
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


def get_git_diff(repo: Repo | None = None) -> str:
    repo = repo or get_repo()
    return repo.git.diff("HEAD")


def generate_commit_with_ai(
    chat_provider: ChatProvider | None,
    local_repo: Repo,
) -> CommitGeneration:
    diff = get_git_diff(local_repo)
    commit_data = generate_commit_message(chat_provider, diff, local_repo.active_branch.name)

    if PREFERENCES.auto_accept_generated_commits:
        return commit_data

    rich.print(f"[grey70]Proposed commit:[/]\n{commit_data.message}\n")

    choices = ["Accept", "Edit", "Exit"]

    proceed_choice = inquirer.select(
        "How would you like to proceed?",
        choices,
    ).execute()

    match proceed_choice:
        case "Accept":
            return commit_data
        case "Edit":
            edited = typer.edit(commit_data.message)
            if edited is None:
                print_error("No description provided")
                raise typer.Exit(1)
            title_with_type = edited.split("\n\n")[0].strip()
            body = edited.split("\n\n")[1].strip()
            return CommitGeneration(
                title=title_with_type.split(":")[1], body=body, type=title_with_type.split(":")[0]
            )
        case _:
            raise typer.Exit(0)


def create_commit(local_repo: Repo, message: str, dry_run: bool = False, retry: int = 0) -> Commit:
    try:
        local_repo.git.add(all=True)
        commit = local_repo.index.commit(message)
        if dry_run:
            local_repo.git.reset("HEAD~1")
        return commit
    except HookExecutionError as err:
        if retry == 0:
            if not dry_run:
                rich.print("[warning]Pre-commit hooks failed, retrying...[/]")
            return create_commit(local_repo, message, dry_run, retry + 1)

        rich.print(err)
        raise typer.Exit(1) from err


def push(local_repo: Repo) -> None:
    try:
        local_repo.git.push("origin", local_repo.active_branch.name)
    except GitCommandError as err:
        rich.print(err)
        raise typer.Exit(1) from err
