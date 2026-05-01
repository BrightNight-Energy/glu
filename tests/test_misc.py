from glu.ai import _trim_text_to_fit_token_limit
from glu.config import MODEL_TOKEN_LIMITS
from glu.jira import filter_creatable_issuetypes, is_forbidden_create_issuetype


def test_trim_text():
    text = "this is a really long text. " * 100
    output = _trim_text_to_fit_token_limit(text, "gpt-4")
    assert len(output) == len(text)

    text = "this is a really long text. " * 1000
    output = _trim_text_to_fit_token_limit(text, "gpt-4")
    assert len(output) == len(text)

    text = "this is a really long text. " * 10_000
    output = _trim_text_to_fit_token_limit(text, "gpt-4")
    assert len(output) == 28765

    text = "this is a really long text. " * 9_000
    output = _trim_text_to_fit_token_limit(text, "gpt-4")
    assert len(output) == 28765

    text = "this is a really long text. " * 10_000
    output = _trim_text_to_fit_token_limit(text, "gemini-1.5-pro-latest")
    assert len(output) == len(text)

    text = "this is a really long text. " * 100
    for model in MODEL_TOKEN_LIMITS:
        output = _trim_text_to_fit_token_limit(text, model)
        assert len(output) == len(text)


def test_epic_issuetype_is_not_creatable():
    assert is_forbidden_create_issuetype("Epic")
    assert is_forbidden_create_issuetype(" epic ")
    assert not is_forbidden_create_issuetype("Story")

    assert filter_creatable_issuetypes(["Bug", "Epic", "Story", "epic"]) == ["Bug", "Story"]
