from types import SimpleNamespace

import pytest

from services.google_translator import GoogleTranslationError, GoogleTransTranslator
from services.text_parser import parse_lyrics


class FakeGoogleClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def translate(self, texts, **kwargs):
        self.calls.append((texts, kwargs))
        if self.error:
            raise self.error
        return self.response


def test_googletrans_batches_nonblank_lines_and_aligns_ids():
    client = FakeGoogleClient(
        [SimpleNamespace(text="你"), SimpleNamespace(text="夜晚")]
    )
    translator = GoogleTransTranslator(translator_factory=lambda: client)
    assert translator.translate(parse_lyrics("君\n\n夜")) == {0: "你", 1: "夜晚"}
    assert client.calls == [(["君", "夜"], {"src": "ja", "dest": "zh-tw"})]


def test_googletrans_translates_one_reference_line():
    client = FakeGoogleClient(SimpleNamespace(text="想見你"))
    translator = GoogleTransTranslator(translator_factory=lambda: client)
    assert translator.translate_line("君に会いたい") == "想見你"


def test_googletrans_wraps_connection_failures():
    client = FakeGoogleClient(error=RuntimeError("blocked"))
    translator = GoogleTransTranslator(translator_factory=lambda: client)
    with pytest.raises(GoogleTranslationError, match="目前無法使用"):
        translator.translate_line("君")
