import json
import os
from json import JSONDecodeError

import rich
import typer
from git import Repo
from github.Repository import Repository
from InquirerPy import inquirer
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_glean import ChatGlean
from pydantic import ValidationError

from glu import ROOT_DIR
from glu.config import JIRA_ISSUE_TEMPLATES, PREFERENCES, REPO_CONFIGS
from glu.models import ChatProvider, CommitGeneration, TicketGeneration
from glu.utils import print_error


def generate_description(
    repo: Repository,
    local_repo: Repo,
    body: str | None,
    chat_provider: ChatProvider | None,
    jira_project: str | None,
) -> str | None:
    chat = _get_chat_model(chat_provider)
    if not chat:
        return None

    template_dir = ".github/pull_request_template.md"
    try:
        template_file = repo.get_contents(template_dir, ref="main")
        if isinstance(template_file, list):
            template = template_file[0].decoded_content.decode() if len(template_file) else None
        else:
            template = template_file.decoded_content.decode()
    except Exception:
        template = None

    if not template:
        if REPO_CONFIGS.get(repo.full_name) and REPO_CONFIGS[repo.full_name].pr_template:
            template = REPO_CONFIGS[repo.full_name].pr_template
        else:
            with open(ROOT_DIR / template_dir, "r", encoding="utf-8") as f:
                template = f.read()
            if jira_project:
                template = template.replace("GLU", jira_project)

    diff = local_repo.git.diff(
        getattr(local_repo.heads, repo.default_branch).commit.hexsha, local_repo.head.commit.hexsha
    )

    prompt = HumanMessage(
        content=f"""
        Provide a description for the PR diff below.

        Be concise and informative about the contents of the PR, relevant to someone
        reviewing the PR. Write the description the following format:
        {template}

        PR body:
        {body or "[None provided]"}

        {diff}
        """
    )

    response = chat.invoke([prompt])

    return response.content  # type: ignore


def generate_ticket(
    repo_name: str | None,
    chat_provider: ChatProvider | None,
    issuetype: str | None = None,
    issuetypes: list[str] | None = None,
    ai_prompt: str | None = None,
    pr_description: str | None = None,
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

    if ai_prompt:
        context = f"user prompt: {ai_prompt}."
    elif pr_description:
        context = f"PR description:\n{pr_description}."
    else:
        print_error("No context provided to generate ticket.")
        raise typer.Exit(1)

    if not issuetype:
        if not issuetypes:
            print_error("No issuetype provided when generating ticket without provided issuetype.")
            raise typer.Exit(1)

        issuetype = _generate_issuetype(chat, issuetypes, context)

    default_template = """
    Description:
    {description}
    """
    template = JIRA_ISSUE_TEMPLATES.get(issuetype.lower(), default_template)

    repo_context = ""
    if repo_name and isinstance(chat, ChatGlean):
        repo_context = f"Tailor your response to the context of the {repo_name} Github repository."

    response_format = {
        "description": "{ticket description}",
        "summary": "{ticket summary, 15 words or less}",
    }

    error = f"Error on previous attempt: {previous_error}" if previous_error else ""
    changes = (
        f"Requested changes from previous generation: {requested_changes}\n\n{
            previous_attempt.model_dump_json()
        }"
        if requested_changes and previous_attempt
        else ""
    )

    prompt = HumanMessage(
        content=f"""
        {error}
        {changes}

        Provide a description and summary for a Jira {issuetype} ticket
        given the {context}.

        The summary should be as specific as possible to the goal of the ticket.

        Be concise in your descriptions, with the goal of providing a clear
        scope of the work to be completed in this ticket. Prefer bullets over paragraphs.

        The format of your description is as follows, where the content in brackets
        needs to be replaced by content:
        {template or ""}

        {repo_context}

        Your response should be in the format of {json.dumps(response_format)}
        """
    )

    response = chat.invoke([prompt])

    try:
        parsed = json.loads(response.content)  # type: ignore
        return TicketGeneration.model_validate(parsed | {"issuetype": issuetype})
    except (JSONDecodeError, ValidationError) as err:
        if isinstance(err, JSONDecodeError):
            error = (
                f"Your response was not in valid JSON format. Make sure it is in format of: "
                f"{json.dumps(response_format)}"
            )
        else:
            error = (
                f"Your response was in invalid format. Make sure it is in format of: "
                f"{json.dumps(response_format)}. Error: {err}"
            )

        return generate_ticket(
            repo_name,
            chat_provider,
            issuetype,
            issuetypes,
            ai_prompt,
            pr_description,
            requested_changes,
            previous_attempt,
            error,
            retry + 1,
        )


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

    if PREFERENCES.preferred_provider in providers:
        return PREFERENCES.preferred_provider

    return inquirer.select("Select provider:", providers).execute()


def generate_commit_message(
    chat_provider: ChatProvider | None,
    diff: str,
    branch_name: str,
    error: str | None = None,
    retry: int = 0,
) -> CommitGeneration:
    if retry > 2:
        print_error(f"Failed to generate commit after {retry} attempts")
        raise typer.Exit(1)

    if not chat_provider:
        print_error("Can't generate commit message with no API key")
        raise typer.Exit(1)

    response_format = {
        "title": "{commit title}",
        "type": "{conventional commit type}",
        "body": "{commit body, bullet-pointed list}",
    }

    prompt = HumanMessage(
        content=f"""
        {error}

        Provide a commit message for the following diff:
        {diff}

        The branch name sometimes gives a hint to the primary objective of the work,
        use it to inform the commit title.

        Be concise in the body, using bullets to give a high level summary. Limit
        to 5 bullets. Focus on the code. Don't mention version bumps of the package itself.

        Your response should be in format of {json.dumps(response_format)}
        """
    )

    chat = _get_chat_model(chat_provider)

    response = chat.invoke([prompt])  # type: ignore

    try:
        parsed = json.loads(response.content)  # type: ignore
        return CommitGeneration.model_validate(parsed)
    except (JSONDecodeError, ValidationError) as err:
        if isinstance(err, JSONDecodeError):
            error = (
                f"Your response was not in valid JSON format. Make sure it is in format of: "
                f"{json.dumps(response_format)}"
            )
        else:
            error = (
                f"Your response was in invalid format. Make sure it is in format of: "
                f"{json.dumps(response_format)}. Error: {err}"
            )

        return generate_commit_message(chat_provider, diff, branch_name, error, retry + 1)


def _generate_issuetype(
    chat: BaseChatModel,
    issuetypes: list[str],
    context: str,
    error: str | None = None,
    retry: int = 0,
) -> str:
    if retry > 2:
        print_error(f"Failed to generate issuetype after {retry} attempts")
        raise typer.Exit(1)

    issuetypes_str = ", ".join(f"'{issuetype}'" for issuetype in issuetypes)

    prompt = HumanMessage(
        content=f"""
        {error}

        Provide the issue type for a Jira ticket
        given the {context}.

        The issue type should be one of: {issuetypes_str}.

        Your response should be simply the issue type, NOTHING else.
        """
    )

    response = chat.invoke([prompt])

    if response.content in (issuetypes or []):
        return response.content  # type: ignore

    error = f"Invalid issuetype: {response.content}. Should be one of: {issuetypes_str}."
    return _generate_issuetype(chat, issuetypes, context, error, retry + 1)


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
