import typer
from git import InvalidGitRepositoryError
from rich.console import Console
from rich.panel import Panel
from rich.table import Column, Table
from rich.text import Text

from glu.gh import get_github_client
from glu.local import get_git_client
from glu.utils import print_error, suppress_traceback


@suppress_traceback
def list_commits(limit: int | None) -> None:
    try:
        git = get_git_client()
    except InvalidGitRepositoryError as err:
        print_error("Not valid a git repository")
        raise typer.Exit(1) from err

    gh = get_github_client(git.repo_name)

    num_commits = min(limit or max(git.get_commit_count_since_checkout(gh.default_branch), 5), 100)

    commits = git.get_commit_log(num_commits)

    commit_table = Table(
        Column(width=19, style="deep_sky_blue1"),
        Column(no_wrap=True),
        Column(no_wrap=True, style="chartreuse3"),
        Column(no_wrap=True, style="yellow1"),
        box=None,
        padding=(0, 1),
        show_header=False,
    )

    for commit in commits:
        commit_table.add_row(
            commit.committed_datetime.astimezone().strftime("%a %b %d %H:%M:%S"),
            commit.summary if isinstance(commit.summary, str) else commit.summary.decode(),
            commit.author.name,
            commit.hexsha[:7],
        )

    console = Console()
    console.print(
        Panel(
            commit_table,
            title=Text(f"Commits ({git.current_branch})"),
            title_align="left",
            expand=False,
            border_style="grey70",
        )
    )
