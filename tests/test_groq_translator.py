import json
from types import SimpleNamespace

import httpx
import pytest
from groq import RateLimitError

from services.groq_translator import GroqTranslationError, GroqTranslator
from services.text_parser import parse_lyrics


class FakeCompletions:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


class EchoCompletions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        payload = json.loads(kwargs["messages"][1]["content"])
        content = json.dumps(
            {
                str(line["id"]): f"翻譯 {line['id']}"
                for line in payload["lines"]
                if line["translate"]
            }
        )
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


def make_client(content=None, error=None):
    completions = FakeCompletions(content, error)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def test_translation_uses_one_strict_request_with_required_id_keys():
    client, calls = make_client(json.dumps({"0": "你", "1": "夜晚"}))

    result = GroqTranslator(client=client).translate(parse_lyrics("君\n\n夜"))

    assert result == {0: "你", 1: "夜晚"}
    assert len(calls.calls) == 1
    call = calls.calls[0]
    assert call["reasoning_effort"] == "low"
    assert call["temperature"] == 0
    response_format = call["response_format"]["json_schema"]
    assert response_format["strict"] is True
    assert response_format["schema"] == {
        "type": "object",
        "properties": {"0": {"type": "string"}, "1": {"type": "string"}},
        "required": ["0", "1"],
        "additionalProperties": False,
    }
    payload = json.loads(call["messages"][1]["content"])
    assert payload == {
        "lines": [
            {"id": 0, "text": "君", "translate": True},
            {"id": 1, "text": "夜", "translate": True},
        ]
    }


def test_pure_rhythmic_chants_stay_in_context_but_not_output_schema():
    lyrics = "\n".join(
        [
            "おどるポンポコリン",
            "ピーヒャラピーヒャラ",
            "パッパパラパ",
            "タッタタラリラ",
            "ピーヒャラ ピー",
        ]
    )
    completions = EchoCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    result = GroqTranslator(client=client).translate(parse_lyrics(lyrics))

    assert result == {
        0: "翻譯 0",
        1: "ピーヒャラピーヒャラ",
        2: "パッパパラパ",
        3: "タッタタラリラ",
        4: "ピーヒャラ ピー",
    }
    call = completions.calls[0]
    payload = json.loads(call["messages"][1]["content"])
    assert [line["translate"] for line in payload["lines"]] == [True, False, False, False, False]
    schema = call["response_format"]["json_schema"]["schema"]
    assert schema["required"] == ["0"]
    assert list(schema["properties"]) == ["0"]


def test_long_lyrics_do_not_trigger_recursive_or_batched_requests():
    lyrics = "\n".join(f"第 {number} 句" for number in range(70))
    completions = EchoCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    result = GroqTranslator(client=client).translate(parse_lyrics(lyrics))

    assert result == {number: f"翻譯 {number}" for number in range(70)}
    assert len(completions.calls) == 1
    schema = completions.calls[0]["response_format"]["json_schema"]["schema"]
    assert schema["required"] == [str(number) for number in range(70)]


@pytest.mark.parametrize(
    "payload",
    [
        {"0": "你"},
        {"0": "你", "1": "夜晚", "9": "未知"},
        {"0": "你", "1": ""},
    ],
)
def test_invalid_strict_response_fails_without_an_automatic_retry(payload):
    client, calls = make_client(json.dumps(payload))

    with pytest.raises(GroqTranslationError):
        GroqTranslator(client=client).translate(parse_lyrics("君\n夜"))

    assert len(calls.calls) == 1


def test_malformed_json_fails_without_an_automatic_retry():
    client, calls = make_client("not-json")

    with pytest.raises(GroqTranslationError, match="格式異常"):
        GroqTranslator(client=client).translate(parse_lyrics("君"))

    assert len(calls.calls) == 1


def test_rate_limit_preserves_retry_after_without_retrying():
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, request=request, headers={"retry-after": "7.2"})
    error = RateLimitError(
        "rate limited",
        response=response,
        body={"error": {"type": "rate_limit_error"}},
    )
    client, calls = make_client(error=error)

    with pytest.raises(GroqTranslationError) as caught:
        GroqTranslator(client=client).translate(parse_lyrics("君"))

    assert caught.value.status_code == 429
    assert caught.value.retry_after == 8
    assert "8 秒後" in caught.value.user_message
    assert len(calls.calls) == 1


def test_special_characters_survive_json_serialization():
    lyrics = "\n".join(["「引用」", '\"風\"', '\"Gott ist tot\"'])
    completions = EchoCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    GroqTranslator(client=client).translate(parse_lyrics(lyrics))

    payload = json.loads(completions.calls[0]["messages"][1]["content"])
    assert [line["text"] for line in payload["lines"]] == lyrics.splitlines()


def test_real_client_disables_automatic_retries():
    received = {}

    def client_factory(**kwargs):
        received.update(kwargs)
        return SimpleNamespace()

    translator = GroqTranslator(api_key="test-key", client_factory=client_factory)

    translator._get_client()

    assert received == {"api_key": "test-key", "max_retries": 0}


def test_regenerate_line_sends_full_context_but_returns_only_target():
    client, calls = make_client(json.dumps({"id": 1, "translation": "我仍想與你相見"}))

    result = GroqTranslator(client=client).regenerate_line(
        parse_lyrics("それでも\n君に会いたい"),
        1,
        {0: "即使如此", 1: "想見你"},
        "更文藝",
    )

    assert result == "我仍想與你相見"
    sent = json.loads(calls.calls[0]["messages"][1]["content"])
    assert sent["lines"] == [
        {"id": 0, "text": "それでも"},
        {"id": 1, "text": "君に会いたい"},
    ]
    assert sent["target_id"] == 1
    assert sent["instruction"] == "更文藝"
    assert calls.calls[0]["temperature"] == 0.45
    assert calls.calls[0]["reasoning_effort"] == "low"


def test_regenerate_line_rejects_wrong_returned_id():
    client, _ = make_client(json.dumps({"id": 0, "translation": "錯的句子"}))

    with pytest.raises(GroqTranslationError, match="格式異常"):
        GroqTranslator(client=client).regenerate_line(
            parse_lyrics("君\n夜"), 1, {0: "你", 1: "夜晚"}
        )

