import datetime as dt
import os

import rich
import typer
from InquirerPy import inquirer
from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_glean import ChatGlean

from glu import ROOT_DIR
from glu.models import ChatProvider
from glu.utils import print_error


def generate_description(
    gh: Github, repo: Repository, pr: PullRequest, chat_provider: ChatProvider | None
) -> str | None:
    chat = _get_chat_model(chat_provider)
    if not chat:
        return None

    template_dir = ".github/pull_request_template.md"
    try:
        template_file = repo.get_contents(template_dir, ref="main")
        if isinstance(template_file, list):
            template = None
        else:
            template = template_file.decoded_content.decode()
    except Exception:
        template = None

    if not template:
        with open(ROOT_DIR / template_dir, "r", encoding="utf-8") as f:
            template = f.read()

    # informs whether to provide the diff or a URL (since indexing should be done)
    is_newly_created_pr = dt.datetime.now(
        dt.timezone.utc
    ) - pr.created_at < dt.timedelta(minutes=15)
    using_glean = isinstance(chat, ChatGlean)

    pr_location = (
        "diff below" if is_newly_created_pr or not using_glean else pr.html_url
    )

    pr_diff_str = ""
    if is_newly_created_pr:
        headers = {"Accept": "application/vnd.github.v3.diff"}
        status, _, diff = gh._Github__requester.requestBlob(  # type: ignore
            "GET", pr.url, headers=headers
        )

        if status != 200:
            print_error(f"Failed to get PR diff ({status})")
            raise typer.Exit(1)

        pr_diff_str = f"PR diff:\n{diff}"

    prompt = HumanMessage(
        content=f"""
        Provide a description for the PR {pr_location}. 
        
        Be concise and informative about the contents of the PR, relevant to someone
        reviewing the PR. Write the description the following format:
        {template}

        PR body:
        {pr.body}

        {pr_diff_str}
        """
    )

    response = chat.invoke([prompt])

    return response.content  # type: ignore


def prompt_for_chat_provider(provider: str | None = None) -> ChatProvider | None:
    providers: list[ChatProvider] = []
    if os.getenv("GLEAN_API_TOKEN"):
        providers.append("Glean")

    if os.getenv("OPENAI_API_KEY"):
        providers.append("OpenAI")

    if provider and provider not in providers:
        print_error(f'No API key found for "{provider}"')
        raise typer.Exit(1)

    if not providers:
        rich.print("[warning]No API key found. Skipping PR description generation.[/]")
        return None

    if len(providers) == 1:
        return providers[0]

    return inquirer.select("Select provider:", providers).execute()


def _get_chat_model(provider: ChatProvider | None) -> BaseChatModel | None:
    match provider:
        case "Glean":
            from langchain_glean.chat_models import ChatGlean

            return ChatGlean()
        case "OpenAI":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model="o4-mini")
        case _:
            return None
