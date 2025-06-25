import os
from pathlib import Path
from typing import Literal, overload

import rich
import typer
from git import Commit, GitCommandError, HookExecutionError, Repo
from InquirerPy import inquirer

from glu.ai import ChatClient, generate_branch_name
from glu.config import PREFERENCES
from glu.models import CommitGeneration
from glu.utils import print_error


class GitClient:
    def __init__(self):
        # get remote repo by parsing .git/config
        cwd = Path.cwd()
        self._repo = Repo(cwd, search_parent_directories=True)

    def get_first_commit_since_checkout(self) -> Commit:
        """
        Return the first commit made on the current branch since it was last checked out.
        If no new commits have been made, returns None.
        """
        head_ref = self._repo.head  # Reference object for HEAD

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
        commits = list(self._repo.iter_commits(rev_range))

        if not commits:
            print_error("Could not find a commit on this branch")
            raise typer.Exit(1)

        # 3) iter_commits returns newest→oldest, so the last item is the _first_ commit
        return commits[-1]

    def remote_branch_in_sync(self, branch: str | None = None, remote_name: str = "origin") -> bool:
        """
        Returns True if:
          - remote_name/branch_name exists, and
          - its commit SHA == the local branch’s commit SHA.
        Returns False otherwise (including if the remote branch doesn’t exist).
        """
        branch_name = branch or self.current_branch

        # 1) Make sure we have up-to-date remote refs
        try:
            self._repo.remotes[remote_name].fetch(branch_name, prune=True)
        except GitCommandError:
            # fetch failed (e.g. no such remote)
            return False

        # 2) Does the remote branch exist?
        remote_ref_name = f"{remote_name}/{branch_name}"
        refs = [ref.name for ref in self._repo.refs]
        if remote_ref_name not in refs:
            return False

        # 3) Compare SHAs
        local_sha = self._repo.heads[branch_name].commit.hexsha
        remote_sha = self._repo.refs[remote_ref_name].commit.hexsha

        return local_sha == remote_sha

    @overload
    def get_diff(self, to: Literal["head"] = "head") -> str: ...

    @overload
    def get_diff(self, to: Literal["main"], default_branch: str) -> str: ...

    def get_diff(
        self, to: Literal["main", "head"] = "head", default_branch: str | None = None
    ) -> str:
        match to:
            case "head":
                return self._repo.git.diff("HEAD")
            case "main" if default_branch:
                return self._repo.git.diff(
                    getattr(self._repo.heads, default_branch).commit.hexsha,
                    self._repo.head.commit.hexsha,
                )
            case _:
                print_error("Diff method not implemented")
                raise typer.Exit(1)

    def create_commit(self, message: str, dry_run: bool = False, retry: int = 0) -> Commit:
        try:
            self._repo.git.add(all=True)
            commit = self._repo.index.commit(message)
            if dry_run:
                self._repo.git.reset("HEAD~1")
            return commit
        except HookExecutionError as err:
            if retry == 0:
                if not dry_run:
                    rich.print("[warning]Pre-commit hooks failed, retrying...[/]")
                return self.create_commit(message, dry_run, retry + 1)

            rich.print(err)
            raise typer.Exit(1) from err

    def push(self) -> None:
        try:
            self._repo.git.push("origin", self._repo.active_branch.name)
        except GitCommandError as err:
            rich.print(err)
            raise typer.Exit(1) from err

    def checkout(self, branch_name: str) -> None:
        self._repo.git.checkout("-b", branch_name)

    def confirm_branch_exists_in_remote(self) -> bool:
        # FIXME: should use github for this purpose
        try:
            self._repo.remotes["origin"].fetch(self.current_branch, prune=True)
            return True
        except GitCommandError:
            return False

    def get_commit_count_since_checkout(self, default_branch: str) -> int:
        main_branch = self._repo.commit(default_branch)
        head_commit = self._repo.head.commit

        return int(self._repo.git.rev_list("--count", head_commit.hexsha, f"^{main_branch.hexsha}"))

    def get_commit_log(self, limit: int) -> list[Commit]:
        return list(self._repo.iter_commits(max_count=limit))

    def get_branch_commit_map(self, default_branch: str) -> dict[str, set[str]]:
        current_branch = self._repo.active_branch.name

        branches_to_check = []
        if current_branch in self._repo.heads:
            branches_to_check.append(self._repo.heads[current_branch])
        if default_branch in self._repo.heads:
            branches_to_check.append(self._repo.heads[default_branch])

        commit_branch_map: dict[str, set[str]] = {}
        for branch in branches_to_check:
            for commit in self._repo.iter_commits(branch, max_count=100):
                commit_branch_map.setdefault(commit.hexsha, set()).add(branch.name)

        return commit_branch_map

    @property
    def repo_name(self) -> str:
        if not len(self._repo.remotes):
            print_error("No remote found for git config")
            raise typer.Exit(1)

        return self._repo.remotes.origin.url.split(":")[1].replace(".git", "")

    @property
    def current_branch(self) -> str:
        return self._repo.active_branch.name

    @property
    def is_dirty(self) -> bool:
        return self._repo.is_dirty()


def get_git_client() -> GitClient:
    if os.getenv("GLU_TEST"):
        from tests.clients.git import FakeGitClient

        return FakeGitClient()  # type: ignore

    return GitClient()


def prompt_commit_edit(commit_data: CommitGeneration) -> CommitGeneration:
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
                title=title_with_type.split(":")[1].strip(),
                body=body,
                type=title_with_type.split(":")[0].strip(),
            )
        case _:
            raise typer.Exit(0)


def checkout_to_branch(
    git: GitClient,
    chat_client: ChatClient,
    main_branch: str,
    commit_message: str | None,
) -> None:
    if git.current_branch != main_branch:
        return  # already checked out

    if not chat_client.is_setup or not commit_message:
        provided_branch_name: str = typer.prompt("Enter branch name")
        branch_name = "-".join(provided_branch_name.split())
    else:
        rich.print("[grey70]Checking out new branch...[/]")
        branch_name = generate_branch_name(chat_client, commit_message)

    git.checkout(branch_name)
