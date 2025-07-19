import webbrowser

import typer
from git import InvalidGitRepositoryError

from glu.local import get_git_client
from glu.utils import print_error, suppress_traceback


@suppress_traceback
def open_pr(
    pr_num: int,
    repo_name: str | None = None,
):
    if not repo_name:
        try:
            git = get_git_client()
            repo_name = git.repo_name
        except InvalidGitRepositoryError as err:
            print_error("Not a valid git repository")
            raise typer.Exit(1) from err

    webbrowser.open(f"https://github.com/{repo_name}/pull/{pr_num}")
