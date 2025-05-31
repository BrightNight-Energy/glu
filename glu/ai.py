import datetime as dt
import json
import os
from json import JSONDecodeError

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
from glu.config import JIRA_ISSUE_TEMPLATES, REPO_CONFIGS
from glu.models import ChatProvider, TicketGeneration
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
        if (
            REPO_CONFIGS.get(repo.full_name)
            and REPO_CONFIGS[repo.full_name].pr_template
        ):
            template = REPO_CONFIGS[repo.full_name].pr_template
        else:
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


def generate_ticket(
    ai_prompt: str,
    issuetype: str,
    repo_name: str | None,
    chat_provider: ChatProvider | None,
    requested_changes: str | None = None,
    previous_attempt: TicketGeneration | None = None,
    previous_error: str | None = None,
    retry: int = 0,
) -> TicketGeneration:
    if retry > 2:
        print_error(f"Failed to generate ticket after {retry} attempts")
        raise typer.Exit(1)

    chat = _get_chat_model(chat_provider)
    if not chat:
        raise typer.Exit(1)

    default_template = """
    Description:
    {description}
    """
    template = JIRA_ISSUE_TEMPLATES.get(issuetype.lower(), default_template)

    repo_context = ""
    if repo_name and isinstance(chat, ChatGlean):
        repo_context = (
            f"Tailor your response to the context of the {repo_name} Github repository."
        )

    response_format = {
        "description": "{ticket description}",
        "summary": "{ticket summary, 15 words or less}",
    }
    error = f"Error on previous attempt: {previous_error}" if previous_error else ""
    changes = (
        f"Requested changes from previous generation: {requested_changes}\n\n{previous_attempt.json()}"
        if requested_changes and previous_attempt
        else ""
    )

    prompt = HumanMessage(
        content=f"""
        {error}
        {changes}
        
        Provide a description and summary for a Jira {issuetype} ticket 
        given the user prompt: {ai_prompt}. 

        The summary should be as specific as possible to the goal of the ticket.

        Be concise and in your descriptions, with the goal of providing a clear
        scope of the work to be completed in this ticket.
        
        The format of your description is as follows, where the content in brackets
        needs to be replaced by content:
        {template or ""}
        
        {repo_context}
        
        Your response should be in format of {json.dumps(response_format)}
        """
    )

    response = chat.invoke([prompt])

    try:
        parsed = json.loads(response.content)  # type: ignore
        if not parsed.get("description") or not parsed.get("summary"):
            error = f"Your response was in invalid format ({parsed}). Make sure it is in format of: {json.dumps(response_format)}"
            return generate_ticket(
                ai_prompt,
                issuetype,
                repo_name,
                chat_provider,
                requested_changes,
                previous_attempt,
                error,
                retry + 1,
            )
    except JSONDecodeError:
        error = f"Your response was not in valid JSON format. Make sure it is in format of: {json.dumps(response_format)}"
        return generate_ticket(
            ai_prompt,
            issuetype,
            repo_name,
            chat_provider,
            requested_changes,
            previous_attempt,
            error,
            retry + 1,
        )

    return TicketGeneration.model_validate(parsed)


def prompt_for_chat_provider(
    provider: str | None = None, raise_if_no_api_key: bool = False
) -> ChatProvider | None:
    providers: list[ChatProvider] = []
    if os.getenv("GLEAN_API_TOKEN"):
        providers.append("Glean")

    if os.getenv("OPENAI_API_KEY"):
        providers.append("OpenAI")

    if provider and provider not in providers:
        print_error(f'No API key found for "{provider}"')
        raise typer.Exit(1)

    if not providers:
        if raise_if_no_api_key:
            print_error("No API key found for AI generation")
            raise typer.Exit(1)

        rich.print("[warning]No API key found for AI generation.[/]")
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
