import re

import rich
import typer
from git import InvalidGitRepositoryError
from rich.console import Console
from rich.emoji import Emoji
from rich.panel import Panel
from rich.table import Column, Table
from rich.text import Text

from glu.gh import get_github_client
from glu.local import get_git_client
from glu.utils import print_error, suppress_traceback


@suppress_traceback
def list_prs(  # noqa: C901
    repo_name: str | None = None,
    only_mine: bool = False,
    no_draft: bool = False,
) -> None:
    if not repo_name:
        try:
            git = get_git_client()
            repo_name = git.repo_name
        except InvalidGitRepositoryError as err:
            print_error("Not a valid git repository")
            raise typer.Exit(1) from err

    gh = get_github_client(repo_name)

    prs = gh.get_prs(only_mine, no_draft)

    if not prs:
        rich.print("Currently no open PRs")
        return

    pr_table = Table(
        Column(style="deep_sky_blue1"),
        Column(no_wrap=True),
        Column(no_wrap=True, style="yellow1"),
        Column(no_wrap=True, style="dodger_blue2"),
        Column(no_wrap=True, style="green3"),
        box=None,
        padding=(0, 1),
        show_header=False,
    )

    def replace_emoji(match):
        emoji_code = match.group(0)
        return Emoji.replace(emoji_code) or emoji_code  # fallback if not valid

    for pr in prs:
        title = Text(pr.title, style="grey46" if pr.draft else "white")
        if pr.labels:
            for label in pr.labels:
                title.append(" ")
                text_with_emojis = re.sub(r":[a-zA-Z0-9_+-]+:", replace_emoji, label.name)
                title.append(Text(f"[{text_with_emojis}]", style=f"on #{label.color}"))

        pr_table.add_row(
            str(pr.number),
            title,
            pr.assignee.login if pr.assignee else "",
            f":speech_balloon:{pr.review_comments}" if pr.review_comments else "",
            f"⍿{pr.commits}",
        )

    console = Console()
    console.print(
        Panel(
            pr_table,
            title=Text(f"PRs ({repo_name})"),
            title_align="left",
            expand=False,
            border_style="grey70",
        )
    )
