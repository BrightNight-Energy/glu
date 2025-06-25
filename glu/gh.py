import os
from typing import Literal, TypeVar

import rich
import typer
from github import Auth, Github, GithubException, UnknownObjectException
from github.CheckRun import CheckRun
from github.Commit import Commit
from github.GithubObject import GithubObject
from github.NamedUser import NamedUser
from github.PaginatedList import PaginatedList
from github.PullRequest import PullRequest
from github.PullRequestReview import PullRequestReview
from thefuzz import fuzz

from glu.config import GITHUB_PAT, REPO_CONFIGS
from glu.models import MatchedUser
from glu.utils import filterable_menu, multi_select_menu, print_error


class GithubClient:
    def __init__(self, repo_name: str):
        auth = Auth.Token(GITHUB_PAT)
        self._client = Github(auth=auth)
        self._repo = self._client.get_repo(repo_name)

    def get_members(self, repo_name: str) -> list[NamedUser]:
        org_name = repo_name.split("/")[0]
        org = self._client.get_organization(org_name)
        members_paginated = org.get_members()

        all_members: list[NamedUser] = []
        for i in range(5):
            members = members_paginated.get_page(i)
            if not members:
                break
            all_members += members

        if not all_members:
            print_error(f"No members found in org {org_name}")
            raise typer.Exit(1)

        return all_members

    def create_pr(
        self,
        current_branch: str,
        title: str,
        body: str | None,
        draft: bool,
    ) -> PullRequest:
        pr = self._repo.create_pull(
            self.default_branch,
            current_branch,
            title=title,
            body=body or "",
            draft=draft,
        )
        pr.add_to_assignees(self._client.get_user().login)
        return pr

    def add_reviewers_to_pr(self, pr: PullRequest, reviewers: list[NamedUser]) -> None:
        for reviewer in reviewers:
            try:
                pr.create_review_request(reviewer.login)
            except GithubException as e:
                print_error(f"Failed to add reviewer {reviewer.login}: {e}")

    def get_contents(self, path: str, ref: str | None = None) -> str | None:
        try:
            file = self._repo.get_contents(path, ref or self.default_branch)
        except UnknownObjectException:
            return None

        if isinstance(file, list):
            return file[0].decoded_content.decode() if len(file) else None

        return file.decoded_content.decode()

    def get_pr(self, number: int) -> PullRequest:
        return self._repo.get_pull(number)

    def get_pr_checks(self, number: int) -> list[CheckRun]:
        pr = self.get_pr(number)
        commits = pr.get_commits()
        last_commit: Commit = commits[commits.totalCount - 1]
        return get_all_from_paginated_list(last_commit.get_check_runs())

    @property
    def delete_branch_on_merge(self) -> bool:
        return self._repo.delete_branch_on_merge

    @property
    def default_branch(self) -> str:
        return self._repo.default_branch


def get_github_client(repo_name: str) -> GithubClient:
    if os.getenv("GLU_TEST"):
        from tests.clients.github import FakeGithubClient

        return FakeGithubClient(repo_name)  # type: ignore

    return GithubClient(repo_name)


def prompt_for_reviewers(
    gh: GithubClient, reviewers: list[str] | None, repo_name: str, draft: bool
) -> list[NamedUser] | None:
    selected_reviewers: list[NamedUser] = []
    if draft:
        return None

    members = gh.get_members(repo_name)
    if not reviewers:
        selected_reviewers_login = multi_select_menu(
            "Select reviewers:",
            [member.login for member in members],
        )
        return [reviewer for reviewer in members if reviewer.login in selected_reviewers_login]

    for i, reviewer in enumerate(reviewers):
        matched_reviewers = [
            MatchedUser(member, fuzz.ratio(reviewer, member.login)) for member in members
        ]
        sorted_reviewers = sorted(matched_reviewers, key=lambda x: x.score, reverse=True)
        if sorted_reviewers[0].score == 100:  # exact match
            selected_reviewers.append(sorted_reviewers[0].user)
            continue

        selected_reviewer_login = filterable_menu(
            f"Select reviewer{f' #{i + 1}' if len(reviewers) > 1 else ''}:",
            [reviewer.user.login for reviewer in sorted_reviewers[:5]],
        )
        selected_reviewer = next(
            reviewer.user
            for reviewer in sorted_reviewers[:5]
            if reviewer.user.login == selected_reviewer_login
        )
        selected_reviewers.append(selected_reviewer)

    return selected_reviewers


def get_repo_name_from_repo_config(project: str) -> str | None:
    if not REPO_CONFIGS:
        return None

    for repo, config in REPO_CONFIGS.items():
        if config.jira_project_key == project:
            return repo

    return None


def get_pr_approval_status(
    paginated_reviews: PaginatedList[PullRequestReview],
) -> Literal["approved", "changes_requested"] | None:
    reviews = get_all_from_paginated_list(paginated_reviews)

    if any(review.state == "CHANGES_REQUESTED" for review in reviews):
        return "changes_requested"

    if any(review.state == "APPROVED" for review in reviews):
        return "approved"

    return None


T = TypeVar("T", bound=GithubObject)


def get_all_from_paginated_list(paginated_list: PaginatedList[T]) -> list[T]:
    items: list[T] = []
    page = 0
    while True:
        items_from_page = paginated_list.get_page(page)
        if not items_from_page:
            break
        items += items_from_page
        page += 1

    return items


def print_status_checks(checks: list[CheckRun]) -> None:  # noqa: C901
    def get_check_attrs(check: CheckRun):  # noqa: C901
        match (check.status, check.conclusion):
            case ("queued", _):
                return ":clock1:", "grey70"
            case ("in_progress", _):
                return ":hourglass:", "grey70"
            case ("completed", "success"):
                return ":white_check_mark:", "green"
            case ("completed", "failure"):
                return ":x:", "red"
            case ("completed", "cancelled"):
                return ":grey_exclamation:", "grey82"
            case ("completed", "neutral"):
                return ":ok:", "grey70"
            case ("completed", "timed_out"):
                return ":alarm_clock:", "orange1"
            case ("completed", "action_required"):
                return ":bust_in_silhouette:", "blue"
            case (_, _):
                return ":question:", "red"

    unique_checks = {check.name: check for check in checks}

    for check_name, check in unique_checks.items():
        emoji, color = get_check_attrs(check)
        rich.print(f"{emoji}  [{color}]{check_name}[/{color}]")
