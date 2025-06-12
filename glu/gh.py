import os

import typer
from github import Auth, Github, GithubException, UnknownObjectException
from github.NamedUser import NamedUser
from github.PullRequest import PullRequest
from thefuzz import fuzz

from glu.config import GITHUB_PAT
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

    @property
    def default_branch(self) -> str:
        return self._repo.default_branch


def get_github_client(repo_name: str) -> GithubClient:
    if os.getenv("GLU_TEST"):
        from tests.conftest import FakeGithubClient

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
