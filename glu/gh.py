import typer
from github import Github
from github.NamedUser import NamedUser
from thefuzz import fuzz

from glu.models import MatchedUser
from glu.utils import filterable_menu, multi_select_menu, print_error


def prompt_for_reviewers(
    gh: Github, reviewers: list[str] | None, repo_name: str, draft: bool
) -> list[NamedUser] | None:
    selected_reviewers: list[NamedUser] = []
    if draft:
        return None

    members = _get_members(gh, repo_name)
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


def _get_members(gh: Github, repo_name: str) -> list[NamedUser]:
    org_name = repo_name.split("/")[0]
    org = gh.get_organization(org_name)
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
