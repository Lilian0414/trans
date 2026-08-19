import asyncio
from collections.abc import Callable
from typing import Any

from googletrans import Translator

from services.text_parser import ParsedLine


class GoogleTranslationError(Exception):
    def __init__(self, user_message: str) -> None:
        super().__init__(user_message)
        self.user_message = user_message


class GoogleTransTranslator:
    """Small adapter around the unofficial googletrans web translator."""

    def __init__(self, translator_factory: Callable[..., Any] = Translator) -> None:
        self._translator_factory = translator_factory

    def translate(self, lines: list[ParsedLine]) -> dict[int, str]:
        source_lines = [line for line in lines if not line.is_blank]
        if not source_lines:
            return {}
        texts = [line.text for line in source_lines]
        translated = self._run(self._translate_many(texts))
        if len(translated) != len(source_lines):
            raise GoogleTranslationError("Google 翻譯結果無法與歌詞對齊，請再試一次。")
        return {line.id: text for line, text in zip(source_lines, translated, strict=True)}

    def translate_line(self, text: str) -> str:
        translated = self._run(self._translate_many([text]))
        if not translated:
            raise GoogleTranslationError("Google 翻譯沒有傳回結果，請再試一次。")
        return translated[0]

    async def _translate_many(self, texts: list[str]) -> list[str]:
        try:
            async with self._translator_factory() as client:
                response = await client.translate(texts, src="ja", dest="zh-tw")
        except Exception as exc:
            raise GoogleTranslationError(
                "Google 翻譯目前無法使用，可能是服務暫時限制連線，請稍後再試。"
            ) from exc

        items = response if isinstance(response, list) else [response]
        translations: list[str] = []
        for item in items:
            text = getattr(item, "text", None)
            if not isinstance(text, str) or not text.strip():
                raise GoogleTranslationError("Google 翻譯結果格式異常，請再試一次。")
            translations.append(text.strip())
        return translations

    @staticmethod
    def _run(coroutine: Any) -> Any:
        try:
            return asyncio.run(coroutine)
        except GoogleTranslationError:
            raise
        except Exception as exc:
            raise GoogleTranslationError("Google 翻譯目前無法使用，請稍後再試。") from exc
