import re
from dataclasses import dataclass
from typing import Literal

from github.NamedUser import NamedUser
from pydantic import BaseModel, model_validator

from glu.utils import capitalize_first_word, load_json

ChatProvider = Literal["OpenAI", "Glean", "Gemini", "Anthropic", "xAI", "Ollama"]

CHAT_PROVIDERS: list[ChatProvider] = ["OpenAI", "Glean", "Gemini", "Anthropic", "xAI", "Ollama"]

TICKET_PLACEHOLDER = "[XY-1234]"


@dataclass
class MatchedUser:
    user: NamedUser
    score: float


class TicketGeneration(BaseModel):
    description: str
    summary: str
    issuetype: str


class PRDescriptionGeneration(BaseModel):
    description: str
    title: str | None = None
    generate_title: bool

    @model_validator(mode="after")
    def validate_title(self) -> "PRDescriptionGeneration":
        if self.generate_title and not self.title:
            raise ValueError("Title is missing")
        if self.title and ":" not in self.title:
            raise ValueError("Title must following conventional commit format")
        return self


class IdReference(BaseModel):
    id: str


@dataclass
class JiraUser:
    accountId: str
    displayName: str


class CommitGeneration(BaseModel):
    title: str
    body: str
    type: str
    formatted_ticket: str | None = None

    @model_validator(mode="after")
    def validate_title(self) -> "CommitGeneration":
        if self.title.count(":") > 1:
            raise ValueError("The char ':' should never appear more than once in the title.")

        type_prefix_pattern = r"^([a-zA-Z0-9_-]+(?:\([^)]+\))?):\s+(.+)"
        if match := re.match(type_prefix_pattern, self.title):
            type_prefix = match.group(1)
            self.title = self.title.replace(f"{type_prefix}:", "").strip()
            self.type = type_prefix

        acceptable_commit_types = load_json("conventional_commit_types.json")
        if not any(
            self.type.startswith(acceptable_type) for acceptable_type in acceptable_commit_types
        ):
            raise ValueError(
                f"Unknown commit type: {self.type}. "
                f"Make sure commit type is one of {', '.join(acceptable_commit_types)}."
            )

        if "/" in self.type:
            raise ValueError("Commit type should not contain the characters: /")

        self.title = capitalize_first_word(self.title)
        return self

    @property
    def full_title(self):
        return f"{self.type}: {self.title}"

    @property
    def message(self):
        message = f"{self.full_title}\n\n{self.body}"
        if self.formatted_ticket:
            message += f"\n\n{self.formatted_ticket}"
        return message
