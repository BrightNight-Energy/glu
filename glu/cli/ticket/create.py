from typing import Any

import rich
import typer
from git import InvalidGitRepositoryError
from InquirerPy import inquirer

from glu.ai import get_ai_client, prompt_for_chat_provider
from glu.config import DEFAULT_JIRA_PROJECT, PREFERENCES
from glu.jira import (
    generate_ticket_with_ai,
    get_jira_client,
    get_jira_project,
    get_user_from_jira,
)
from glu.local import get_git_client
from glu.utils import add_generated_with_glu_tag, prompt_or_edit, suppress_traceback


@suppress_traceback
def create_ticket(
    summary: str | None,
    issue_type: str | None,
    body: str | None,
    assignee: str | None,
    reporter: str | None,
    priority: str | None,
    project: str | None,
    ai_prompt: str | None,
    provider: str | None,
    model: str | None,
    **extra_fields: Any,
):
    jira = get_jira_client()

    try:
        repo_name = get_git_client().repo_name
    except InvalidGitRepositoryError:
        repo_name = None

    project = project or DEFAULT_JIRA_PROJECT
    if not project:
        project = get_jira_project(jira, repo_name)

    types = jira.get_issuetypes(project or "")
    if not issue_type:
        issuetype = inquirer.select("Select type:", types).execute()
    else:
        if issue_type.title() not in types:
            issuetype = inquirer.select("Select type:", types).execute()
        else:
            issuetype = issue_type

    if ai_prompt:
        # typer does not currently support union types
        # once they do, the below will work
        # keep an eye on: https://github.com/fastapi/typer/pull/1148
        # if isinstance(ai_prompt, bool):
        #     prompt = prompt_or_edit('AI Prompt')
        # else:
        # prompt = ai_prompt

        chat_client = get_ai_client(model)
        provider = prompt_for_chat_provider(chat_client, provider, True)
        chat_client.set_chat_model(provider)
        ticket_data = generate_ticket_with_ai(
            chat_client, repo_name, issuetype, ai_prompt=ai_prompt
        )
        summary = ticket_data.summary
        body = ticket_data.description
        if body and PREFERENCES.add_generated_with_glu_tag:
            body = add_generated_with_glu_tag(body, supports_markdown=False)
    else:
        if not summary:
            summary = typer.prompt(
                "Summary",
                show_default=False,
            )

        if not body:
            body = prompt_or_edit("Description", allow_skip=True)

    reporter_ref = get_user_from_jira(jira, reporter, "reporter")

    assignee_ref = get_user_from_jira(jira, assignee, "assignee")

    if priority:
        extra_fields["priority"] = priority

    issue = jira.create_ticket(
        project, issuetype, summary or "", body, reporter_ref, assignee_ref, **extra_fields
    )

    rich.print(f":page_with_curl: Created issue [bold red]{issue.key}[/]")
    rich.print(f"View at {issue.permalink()}")
