from dataclasses import dataclass
from typing import Literal

from github.NamedUser import NamedUser
from pydantic import BaseModel, model_validator

from glu.utils import capitalize_first_word

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

        if self.type in self.title:
            self.title = self.title.split(":")[1].strip()

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
