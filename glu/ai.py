import json
import os
import re
from json import JSONDecodeError

import rich
import tiktoken
import typer
from InquirerPy import inquirer
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from pydantic import ValidationError

from glu import ROOT_DIR
from glu.config import (
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_XAI_MODEL,
    JIRA_ISSUE_TEMPLATES,
    MODEL_TOKEN_LIMITS,
    PREFERENCES,
    REPO_CONFIGS,
)
from glu.models import TICKET_PLACEHOLDER, ChatProvider, CommitGeneration, TicketGeneration
from glu.utils import print_error, remove_json_backticks


class ChatClient:
    providers: list[ChatProvider] = []
    _model: str | None = None
    _client: BaseChatModel | None = None

    def __init__(self, model: str | None):
        # if os.getenv("GLEAN_API_TOKEN"): # currently not supported
        #     providers.append("Glean")

        if os.getenv("OPENAI_API_KEY"):
            self.providers.append("OpenAI")

        if os.getenv("GOOGLE_API_KEY"):
            self.providers.append("Gemini")

        if os.getenv("ANTHROPIC_API_KEY"):
            self.providers.append("Anthropic")

        if os.getenv("XAI_API_KEY"):
            self.providers.append("xAI")

        self.providers.append("Ollama")

        self._model = model

    def run(self, msg: str) -> str:
        if not self._client:
            print_error("No chat model set for AI generation")
            raise typer.Exit(1)

        prompt = HumanMessage(msg)

        response = self._client.invoke([prompt])

        return response.content  # type: ignore

    def set_chat_model(self, provider: ChatProvider | None) -> None:
        match provider:
            case "Glean":
                from langchain_glean.chat_models import ChatGlean

                self._client = ChatGlean()
            case "OpenAI":
                from langchain_openai import ChatOpenAI
                from openai import OpenAI

                client = OpenAI()
                self._model = self._model or DEFAULT_OPENAI_MODEL
                models = [model.id for model in client.models.list()]
                if self._model not in models:
                    print_error(f"Invalid model for OpenAI: {self._model}")
                    raise typer.Exit()
                self._client = ChatOpenAI(model=self._model)
            case "Gemini":
                from langchain_google_genai import ChatGoogleGenerativeAI

                self._model = self._model or DEFAULT_GEMINI_MODEL
                self._client = ChatGoogleGenerativeAI(model=self._model)
            case "Anthropic":
                from langchain_anthropic.chat_models import ChatAnthropic

                self._model = self._model or DEFAULT_ANTHROPIC_MODEL
                self._client = ChatAnthropic(model_name=self._model, timeout=None, stop=None)
            case "Ollama":
                from langchain_ollama.chat_models import ChatOllama

                self._model = self._model or DEFAULT_OLLAMA_MODEL
                self._client = ChatOllama(model=self._model)
            case "xAI":
                from langchain_xai.chat_models import ChatXAI

                self._model = self._model or DEFAULT_XAI_MODEL
                self._client = ChatXAI(model=self._model)

    @property
    def is_setup(self) -> bool:
        return bool(self._client)

    @property
    def model(self) -> str:
        if not self._model:
            print_error("No model set for AI generation")
            raise typer.Exit(1)
        return self._model


def get_ai_client(model: str | None) -> ChatClient:
    if os.getenv("GLU_TEST"):
        from tests.clients.ai import FakeChatClient

        return FakeChatClient(model)  # type: ignore

    return ChatClient(model)


def generate_description(
    chat_client: ChatClient,
    template: str | None,
    repo_name: str,
    diff: str,
    body: str | None,
    error: str | None = None,
    retry: int = 0,
) -> str | None:
    if retry > 2:
        print_error(f"Failed to generate description after {retry} attempts")
        raise typer.Exit(1)

    template_dir = ".github/pull_request_template.md"
    if not template:
        if REPO_CONFIGS.get(repo_name) and REPO_CONFIGS[repo_name].pr_template:
            template_text: str = REPO_CONFIGS[repo_name].pr_template  # type: ignore
        else:
            with open(ROOT_DIR / template_dir, "r", encoding="utf-8") as f:
                template_text = f.read()
    else:
        template_text = template

    ticket_placeholder_pattern = r"\[[A-Z]{2,}-[A-Z0-9]+]"
    ticket_placeholder_match = re.search(ticket_placeholder_pattern, template_text)

    prompt = f"""
    {f"Previous error: {error}" if error else ""}

    Provide a description for the PR diff below.

    Be concise and informative about the contents of the PR, relevant to someone
    reviewing the PR. Don't describe changes to testing, unless testing is the main
    purpose for the PR. Leave any Jira ticket placeholder as it was in the template.
    Write the description using the following template:
    {template}

    PR body:
    {body or "[None provided]"}

    {_trim_text_to_fit_token_limit(diff, chat_client.model)}
    """

    response = chat_client.run(prompt)

    if ticket_placeholder_match:
        template_placeholder = template_text[
            ticket_placeholder_match.start() : ticket_placeholder_match.end()
        ]
        if template_placeholder not in response:
            error = (
                f"The ticket placeholder '{template_placeholder}' was not found in the response."
            )
            return generate_description(
                chat_client, template, repo_name, diff, body, error, retry + 1
            )

        return re.sub(ticket_placeholder_pattern, TICKET_PLACEHOLDER, response)

    return response


def generate_ticket(
    chat_client: ChatClient,
    repo_name: str | None,
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

        issuetype = _generate_issuetype(chat_client, issuetypes, context)

    default_template = """
    Description:
    {description}
    """
    template = JIRA_ISSUE_TEMPLATES.get(issuetype.lower(), default_template)

    response_format = {
        "description": "{ticket description}",
        "summary": "{ticket summary, 15 words or less}",
    }

    error = f"Error on previous attempt: {previous_error}" if previous_error else ""
    changes = (
        f"Requested changes from previous generation: "
        f"{requested_changes}\n\n{previous_attempt.model_dump_json()}"
        if requested_changes and previous_attempt
        else ""
    )

    prompt = f"""
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

    Your response should be in the format of {json.dumps(response_format)}
    """

    response = chat_client.run(prompt)

    try:
        parsed = json.loads(remove_json_backticks(response))
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
            chat_client,
            repo_name,
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
    chat_client: ChatClient, provider: str | None = None, raise_if_no_api_key: bool = False
) -> ChatProvider | None:
    providers = chat_client.providers

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
    chat_client: ChatClient,
    diff: str,
    branch_name: str,
    error: str | None = None,
    retry: int = 0,
) -> CommitGeneration:
    if retry > 2:
        print_error(f"Failed to generate commit after {retry} attempts")
        raise typer.Exit(1)

    response_format = {
        "title": "{commit title}",
        "type": "{conventional commit type}",
        "body": "{commit body, bullet-pointed list}",
    }

    prompt = f"""
    {error}

    Provide a commit message for the following diff:
    {_trim_text_to_fit_token_limit(diff, chat_client.model)}

    The branch name sometimes gives a hint to the primary objective of the work,
    use it to inform the commit title.

    Be concise in the body, using bullets to give a high level summary. Limit
    to 5 bullets. Focus on the code. Don't mention version bumps of the package itself.

    Your response should be in format of {json.dumps(response_format)}
    """

    response = chat_client.run(prompt)

    try:
        parsed = json.loads(remove_json_backticks(response))
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

        return generate_commit_message(chat_client, diff, branch_name, error, retry + 1)


def generate_branch_name(
    chat_client: ChatClient,
    commit_message: str,
) -> str:
    prompt = f"""
    Generate a branch name for the following commit:
    {commit_message}

    The branch name should be separated by '-' and be max 5 words.

    Your response should be simply the branch name, NOTHING else.
    """

    return chat_client.run(prompt)


def generate_final_commit_message(
    chat_client: ChatClient,
    summary_commit_message: str,
    formatted_ticket: str | None,
    pr_description: str,
    error: str | None = None,
    retry: int = 0,
) -> CommitGeneration:
    response_format = {
        "title": "{commit title}",
        "type": "{conventional commit type}",
        "body": "{commit body, bullet-pointed list}",
    }

    prompt = f"""
    {f"Previous error: {error}"}

    Provide a commit message for merge into the repo.
    Here's the commit messages of all previous commits:
    {summary_commit_message}

    Here's the PR description:
    {pr_description}

    The branch name sometimes gives a hint to the primary objective of the work,
    use it to inform the commit title.

    Be concise in the body, using bullets to give a high level summary. Limit
    to 5-10 bullets. Don't mention version bumps of the package itself or
    testing changes unless testing is the primary purpose of the PR.
    """

    response = chat_client.run(prompt)

    try:
        parsed = json.loads(remove_json_backticks(response))
        return CommitGeneration.model_validate(parsed | {"formatted_ticket": formatted_ticket})
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

        return generate_final_commit_message(
            chat_client, summary_commit_message, formatted_ticket, pr_description, error, retry + 1
        )


def _trim_text_to_fit_token_limit(text: str, model: str, buffer_tokens: int = 1000) -> str:
    max_tokens = MODEL_TOKEN_LIMITS.get(model, 200_000) - buffer_tokens
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # Use cl100k_base as fallback for Anthropic, Gemini, xAI, etc.
        encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    return encoding.decode(tokens[:max_tokens])


def _generate_issuetype(
    chat_client: ChatClient,
    issuetypes: list[str],
    context: str,
    error: str | None = None,
    retry: int = 0,
) -> str:
    if retry > 2:
        print_error(f"Failed to generate issuetype after {retry} attempts")
        raise typer.Exit(1)

    issuetypes_str = ", ".join(f"'{issuetype}'" for issuetype in issuetypes)

    prompt = f"""
    {error}

    Provide the issue type for a Jira ticket given the {context}.

    The issue type should be one of: {issuetypes_str}.

    Your response should be simply the issue type, NOTHING else.
    """

    response = chat_client.run(prompt)

    if response in (issuetypes or []):
        return response

    error = f"Invalid issuetype: {response}. Should be one of: {issuetypes_str}."
    return _generate_issuetype(chat_client, issuetypes, context, error, retry + 1)
