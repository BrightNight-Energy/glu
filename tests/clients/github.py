# ruff: noqa: ARG002, E501, C901
import datetime as dt
import os
import random
from dataclasses import dataclass

from git import Commit
from github.CheckRun import CheckRun
from github.NamedUser import NamedUser
from github.PaginatedList import PaginatedList
from github.PullRequest import PullRequest
from github.PullRequestReview import PullRequestReview
from pydantic import BaseModel, TypeAdapter

from glu import ROOT_DIR
from tests.utils import load_json


class FakeGithubClient:
    def __init__(self, repo_name: str):
        pass

    def get_members(self, repo_name: str) -> list[NamedUser]:
        @dataclass
        class FakeUser:
            login: str

        return [FakeUser("teddy"), FakeUser("jack"), FakeUser("peter")]  # type: ignore

    def create_pr(
        self,
        current_branch: str,
        title: str,
        body: str | None,
        draft: bool,
    ) -> PullRequest:
        @dataclass
        class FakePullRequest:
            number: int

        return FakePullRequest(random.randint(1000, 10_000))  # type: ignore

    def add_reviewers_to_pr(self, pr: PullRequest, reviewers: list[NamedUser]) -> None:
        pass

    def get_contents(self, path: str, ref: str | None = None) -> str | None:
        if os.getenv("HAS_REPO_TEMPLATE"):
            with open(ROOT_DIR / ".github" / "pull_request_template.md", "r") as f:
                return f.read()

        return None

    def get_pr(self, number: int) -> PullRequest:
        class FakePullRequest(BaseModel):
            number: int
            title: str
            body: str | None
            changed_files: int
            id: int
            mergeable: bool
            mergeable_state: str
            merged: bool
            updated_at: str
            state: str
            draft: bool

            def get_commits(self) -> list[Commit]:
                class FakeCommit(BaseModel):
                    message: str

                class FakeCommitRef(BaseModel):
                    commit: FakeCommit

                @dataclass
                class PaginatedList:
                    totalCount: int

                    def get_page(self, page: int) -> list[PullRequestReview]:
                        if page > 0:
                            return []

                        prev_commits = load_json("previous_commit_messages.json")
                        commits = [{"commit": {"message": message}} for message in prev_commits]

                        return TypeAdapter(list[FakeCommitRef]).validate_python(commits)  # type: ignore

                return PaginatedList(4)  # type: ignore

            def merge(
                self, commit_message: str, commit_title: str, merge_method: str, delete_branch: bool
            ) -> None:
                pass

            def get_reviews(self) -> PaginatedList[PullRequestReview]:
                class NamedUser(BaseModel):
                    login: str

                class PRReview(BaseModel):
                    id: int
                    body: str | None
                    state: str
                    user: NamedUser

                @dataclass
                class PaginatedList:
                    totalCount: int

                    def get_page(self, page: int) -> list[PullRequestReview]:
                        if page > 0:
                            return []

                        pr_reviews = load_json("pr_reviews.json")
                        if os.getenv("IS_PR_NOT_APPROVED"):
                            pr_reviews.pop(-1)
                        if os.getenv("PR_CHANGES_REQUESTED"):
                            pr_reviews[1]["state"] = "CHANGES_REQUESTED"
                            pr_reviews[1]["body"] = "meh /:"

                        return TypeAdapter(list[PRReview]).validate_python(pr_reviews)  # type: ignore

                return PaginatedList(2)  # type: ignore

            def mark_ready_for_review(self):
                pass

        pr_data = load_json("pr_data.json")
        if os.getenv("PR_NOT_MERGEABLE"):
            pr_data["mergeable"] = False
            pr_data["mergeable_state"] = "dirty"

        if os.getenv("IS_PR_MERGED"):
            pr_data["merged"] = True

        if os.getenv("IS_DRAFT_PR"):
            pr_data["draft"] = True

        if os.getenv("PR_HAS_NO_TICKET"):
            pr_data["body"] = None

        return FakePullRequest.model_validate(pr_data)  # type: ignore

    def get_pr_checks(self, number: int) -> list[CheckRun]:
        class FakeCheckRun(BaseModel):
            id: int
            status: str
            completed: bool
            conclusion: str | None
            name: str
            started_at: dt.datetime

        checks = load_json("cicd_run_checks.json")
        if os.getenv("IS_CICD_FAILING"):
            checks[-1]["conclusion"] = "failure"

        return TypeAdapter(list[FakeCheckRun]).validate_python(checks)  # type: ignore

    @property
    def delete_branch_on_merge(self) -> bool:
        return False

    @property
    def default_branch(self) -> str:
        return "main"
