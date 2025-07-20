import typer
from git import InvalidGitRepositoryError
from rich.console import Group
from rich.markdown import Markdown
from rich.text import Text

from glu.gh import get_github_client
from glu.local import get_git_client
from glu.utils import print_panel, replace_emoji, suppress_traceback


@suppress_traceback
def view_pr(
    pr_num: int,
    repo_name: str | None,
) -> None:
    if not repo_name:
        try:
            git = get_git_client()
            repo_name = git.repo_name
        except InvalidGitRepositoryError:
            repo_name = ""

        if not repo_name:
            repo_name = f"{typer.prompt('Enter org name')}/{typer.prompt('Enter repo name')}"

    gh = get_github_client(repo_name)

    pr = gh.get_pr(pr_num)

    border_style = "bright_white"
    state = pr.state.title()
    if pr.draft:
        border_style = "grey70"
        state = "Draft"
    elif pr.merged:
        border_style = "medium_orchid"
    elif pr.state == "closed":
        border_style = "red"

    state_style_kwarg = (
        {"style": f"on {border_style}"} if border_style not in ["bright_white", "grey70"] else {}
    )
    reviewers = (
        ", ".join(reviewer.login for reviewer in pr.requested_reviewers)
        if pr.requested_reviewers
        else "[None]"
    )

    comments = pr.comments
    renderables = [
        Markdown(f"## {pr.title}", style="bright_white"),
        "\n",
        Markdown(pr.body),
        "\n",
        Text(state, **state_style_kwarg),  # type: ignore
        Text("Assignee: ", style="grey70") + Text(pr.assignee.login, style="yellow1"),
        Text("Reviewers: ", style="grey70") + Text(reviewers, style="dodger_blue1"),
        Text(f"⍿ {pr.head.ref} ({pr.commits})", style="green3"),
    ]
    if comments:
        text_with_emojis = replace_emoji(f" {':speech_balloon:'} {pr.comments}")
        renderables.append(Text(text_with_emojis))

    renderable_group = Group(*renderables)  # type: ignore
    print_panel(f"PR #{pr_num}", renderable_group, border_style)
