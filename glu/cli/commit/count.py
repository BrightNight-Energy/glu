import rich
import typer
from git import InvalidGitRepositoryError

from glu.gh import get_github_client
from glu.local import get_git_client
from glu.utils import print_error, suppress_traceback


@suppress_traceback
def count_commits(branch: str | None) -> None:
    try:
        git = get_git_client()
    except InvalidGitRepositoryError as err:
        print_error("Not valid a git repository")
        raise typer.Exit(1) from err

    if branch:
        branch_name = branch
    else:
        gh = get_github_client(git.repo_name)
        branch_name = gh.default_branch

    num_commits = git.get_commit_count_since_checkout(branch_name)

    rich.print(f"Commits since [bold blue]{branch_name}[/]: [bold green]{num_commits}[/]")
