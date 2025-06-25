# ruff: noqa: ARG002, E501, C901
import datetime as dt
import os
from dataclasses import dataclass
from typing import Literal, overload

from git import Commit, HookExecutionError
from pydantic import BaseModel, TypeAdapter

from tests import TESTS_DATA_DIR
from tests.utils import load_json


class FakeGitClient:
    def get_first_commit_since_checkout(self) -> Commit:
        @dataclass
        class FakeCommit:
            message: str

            @property
            def summary(self) -> str:
                return self.message.split("\n")[0]

        return FakeCommit("feat: Add testing to my CLI app")  # type: ignore

    def remote_branch_in_sync(self, branch: str | None = None, remote_name: str = "origin") -> bool:
        return os.getenv("IS_REMOTE_BRANCH_IN_SYNC") == "1"

    @overload
    def get_diff(self, to: Literal["head"]) -> str: ...

    @overload
    def get_diff(self, to: Literal["main"], default_branch: str) -> str: ...

    def get_diff(
        self, to: Literal["main", "head"] = "head", default_branch: str | None = None
    ) -> str:
        with open(TESTS_DATA_DIR / "diff_to_main.txt", "r") as f:
            return f.read()

    def create_commit(self, message: str, dry_run: bool = False, retry: int = 0) -> Commit:
        if os.getenv("RAISE_HOOK_EXECUTION_ERROR"):
            raise HookExecutionError(
                "commit",
                """
            glu/local.py:275:19: ARG001 Unused function argument: `git`
                |
            275 | def create_commit(git: Git, message: str, dry_run: bool = False, retry: int = 0) -> Commit:
                |                   ^^^ ARG001
            276 |     try:
            277 |         local_repo.git.add(all=True)
                |
            """,
            )

        @dataclass
        class FakeCommit:
            summary: str
            message: str

        return FakeCommit(  # type: ignore
            "feat: Add testing to my CLI app",
            "- Add testing through pexpect and pytest\n- Added very many good tests",
        )

    def push(self) -> None:
        os.environ["IS_REMOTE_BRANCH_IN_SYNC"] = "1"
        pass

    def checkout(self, branch_name: str) -> None:
        pass

    def confirm_branch_exists_in_remote(self) -> bool:
        return True

    def get_commit_count_since_checkout(self, default_branch: str) -> int:
        return 5

    def get_commit_log(self, limit: int) -> list[Commit]:
        class CommitAuthor(BaseModel):
            name: str

        class FakeCommit(BaseModel):
            author: CommitAuthor
            summary: str
            hexsha: str
            committed_datetime: dt.datetime

        return TypeAdapter(list[FakeCommit]).validate_python(load_json("list_commits.json"))  # type: ignore

    def get_branch_commit_map(self, default_branch: str) -> dict[str, set[str]]:
        commit_branch_map = load_json("commit_branch_map.json")
        return {k: set(v) for k, v in commit_branch_map.items()}

    @property
    def repo_name(self) -> str:
        return "github/Test-Repo"

    @property
    def current_branch(self) -> str:
        return "add-tests"

    @property
    def is_dirty(self) -> bool:
        return os.getenv("IS_GIT_DIRTY") == "1"
