import webbrowser

import typer
from git import InvalidGitRepositoryError

from glu.config import JIRA_SERVER
from glu.jira import get_jira_client, get_jira_project
from glu.local import get_git_client
from glu.utils import print_error, suppress_traceback


@suppress_traceback
def open_ticket(
    ticket_num: int,
    project: str | None = None,
):
    jira = get_jira_client()
    if not project:
        try:
            git = get_git_client()
            repo_name = git.repo_name
        except InvalidGitRepositoryError as err:
            print_error("Not a valid git repository. Specify Jira project name")
            raise typer.Exit(1) from err

        jira_project = get_jira_project(jira, repo_name, project)
    else:
        jira_project = project

    webbrowser.open(f"{JIRA_SERVER}/browse/{jira_project}-{ticket_num}")
