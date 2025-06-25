# ruff: noqa: ARG002, E501, C901
import json
import os

from langchain_core.language_models import BaseChatModel

from glu.models import ChatProvider
from tests import TESTS_DATA_DIR
from tests.utils import load_json


class FakeChatClient:
    providers: list[ChatProvider] = []
    model: str | None = None
    _client: BaseChatModel | None = None

    def __init__(self, model: str | None):
        self.providers = ["OpenAI", "Ollama"]
        self.model = os.getenv("GLU_TEST_MODEL", "o4-mini")

    def run(self, msg: str) -> str:
        if "adding testing" in msg:
            return json.dumps(load_json("ai_ticket.json"))
        if "Provide a commit message for the following diff" in msg:
            return json.dumps(load_json("commit_message.json"))
        if "Provide the issue type for a Jira ticket" in msg:
            return "Chore"
        if "Provide a description and summary for a Jira" in msg:
            return json.dumps(load_json("ai_ticket.json"))
        if "Provide a description for the PR diff below." in msg:
            with open(TESTS_DATA_DIR / "pr_description.txt", "r") as f:
                return f.read()
        if "Provide a commit message for merge into the repo." in msg:
            return json.dumps(load_json("final_commit_message.json"))
        raise NotImplementedError("AI test message not implemented")

    def set_chat_model(self, provider: ChatProvider | None) -> None:
        pass
