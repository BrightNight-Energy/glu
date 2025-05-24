import typer
from github import Github
from github.NamedUser import NamedUser

from glu.utils import print_error


def get_members(gh: Github, repo_name: str) -> list[NamedUser]:
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
