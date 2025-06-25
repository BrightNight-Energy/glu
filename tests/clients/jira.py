# ruff: noqa: ARG002, E501, C901
import os
import random
from dataclasses import dataclass

from jira import Issue, Project

from glu.config import JIRA_SERVER
from glu.models import IdReference, JiraUser


class FakeJiraClient:
    def myself(self) -> JiraUser:
        return JiraUser("2662", "peter")

    def projects(self) -> list[Project]:
        @dataclass
        class FakeProject:
            key: str

        return [FakeProject("TEST"), FakeProject("GLU")]  # type: ignore

    def search_users(self, query: str) -> list[JiraUser]:
        return [
            JiraUser("5234", "jack"),
            JiraUser("3462", "teddy"),
            JiraUser("55462", "sarah"),
        ]

    def get_issuetypes(self, project: str) -> list[str]:
        return ["Bug", "Story", "Spike", "Chore", "Subtask"]

    def get_transitions(self, ticket_id: str) -> list[str]:
        if os.getenv("IS_JIRA_TICKET_IN_TO_DO"):
            return ["Starting"]
        if os.getenv("IS_JIRA_TICKET_IN_PROGRESS"):
            return ["Ready for review"]

        return []

    def transition_issue(self, ticket_id: str, transition: str) -> None:
        pass

    def create_ticket(
        self,
        project: str,
        issuetype: str,
        summary: str,
        description: str | None,
        reporter_ref: IdReference,
        assignee_ref: IdReference,
        **extra_fields: dict,
    ) -> Issue:
        @dataclass
        class FakeTicket:
            key: str

            def permalink(self) -> str:
                return f"{JIRA_SERVER}/browse/{self.key}"

        new_ticket = f"{project}-{random.randint(100, 1000)}"
        return FakeTicket(new_ticket)  # type: ignore
