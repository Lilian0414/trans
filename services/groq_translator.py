import json
import logging
import math
import os
from collections.abc import Callable
from typing import Any

from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq, RateLimitError

from services.text_parser import ParsedLine

DEFAULT_MODEL = "openai/gpt-oss-20b"
DEFAULT_TIMEOUT_SECONDS = 20.0

PRESERVED_CHANT_LINES = {
    "タッタタラリラ",
    "ピーヒャラピーヒャラ",
    "ピーヒャラピー",
    "パッパパラパ",
}

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是專業的日文歌詞翻譯者。請閱讀 lines 提供的整首歌詞上下文，只翻譯 translate 為 true 的行，並以自然、符合台灣用語的繁體中文呈現。妥善處理代名詞、語氣、比喻與省略；沒有實際語義、用來維持旋律或節奏的擬聲詞與唱詞請原樣保留日文。輸出格式由 JSON Schema 規定：每個鍵都是原始行 ID 的十進位字串，每個值都是該行譯文。不得合併、拆分、遺漏或新增任何 ID。"""

REGENERATE_SYSTEM_PROMPT = """你是專業的日文歌詞翻譯編輯。請閱讀完整歌詞與目前譯文，依照上下文和使用者指定的風格，只重新翻譯 target_id 指定的單一句。輸出自然、符合台灣用語的繁體中文；沒有實際語義、用來維持旋律或節奏的擬聲詞與唱詞請原樣保留日文。只輸出指定 JSON，不要加入說明，不得修改 id。"""


class GroqTranslationError(Exception):
    def __init__(
        self,
        user_message: str,
        *,
        status_code: int = 502,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code
        self.retry_after = retry_after


class GroqTranslator:
    def __init__(
        self,
        client: Any | None = None,
        *,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client_factory: Callable[..., Any] = Groq,
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._client_factory = client_factory

    def translate(self, lines: list[ParsedLine]) -> dict[int, str]:
        source_lines = [line for line in lines if not line.is_blank]
        if not source_lines:
            return {}

        translations: dict[int, str] = {}
        translatable_lines: list[ParsedLine] = []
        for line in source_lines:
            assert line.id is not None
            if self._is_preserved_chant_line(line.text):
                translations[line.id] = line.text
            else:
                translatable_lines.append(line)

        if translatable_lines:
            translations.update(self._translate_once(translatable_lines, source_lines))
        return translations

    @staticmethod
    def _is_preserved_chant_line(text: str) -> bool:
        return "".join(text.split()) in PRESERVED_CHANT_LINES

    def _translate_once(
        self,
        target_lines: list[ParsedLine],
        context_lines: list[ParsedLine],
    ) -> dict[int, str]:
        target_ids = {line.id for line in target_lines}
        payload = {
            "lines": [
                {
                    "id": line.id,
                    "text": line.text,
                    "translate": line.id in target_ids,
                }
                for line in context_lines
            ]
        }
        response_format = self._translation_response_format(target_lines)

        try:
            completion = self._get_client().chat.completions.create(
                model=self._model or os.getenv("GROQ_MODEL", DEFAULT_MODEL),
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                response_format=response_format,
                reasoning_effort="low",
                temperature=0,
                timeout=self._timeout,
            )
        except RateLimitError as exc:
            error = self._rate_limit_error(exc)
            logger.warning(
                "Groq rate limit hit line_count=%s retry_after=%s",
                len(target_lines),
                error.retry_after,
            )
            raise error from exc
        except APITimeoutError as exc:
            raise GroqTranslationError("翻譯等待時間過長，請稍後再試。", status_code=504) from exc
        except APIConnectionError as exc:
            raise GroqTranslationError("暫時無法連線到翻譯服務，請稍後再試。", status_code=503) from exc
        except APIStatusError as exc:
            error_type, error_code = self._safe_status_error_details(exc)
            logger.error(
                "Groq request failed line_count=%s status=%s error_type=%s error_code=%s",
                len(target_lines),
                exc.status_code,
                error_type,
                error_code,
            )
            raise GroqTranslationError("翻譯服務暫時無法使用，請稍後再試。") from exc
        except Exception as exc:
            raise GroqTranslationError("翻譯服務發生問題，請稍後再試。") from exc

        try:
            content = completion.choices[0].message.content
            data = json.loads(content)
            return self._validate_response(data, target_lines)
        except GroqTranslationError:
            raise
        except (AttributeError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.error("Groq strict response could not be parsed line_count=%s", len(target_lines))
            raise GroqTranslationError("翻譯結果格式異常，請稍後再試。") from exc

    @staticmethod
    def _translation_response_format(lines: list[ParsedLine]) -> dict[str, Any]:
        ids = [str(line.id) for line in lines]
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "lyrics_translation",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {line_id: {"type": "string"} for line_id in ids},
                    "required": ids,
                    "additionalProperties": False,
                },
            },
        }

    @staticmethod
    def _retry_after_seconds(exc: RateLimitError) -> int | None:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        raw_value = headers.get("retry-after") if headers is not None else None
        if raw_value is None:
            return None
        try:
            return max(1, math.ceil(float(raw_value)))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _rate_limit_error(cls, exc: RateLimitError) -> GroqTranslationError:
        retry_after = cls._retry_after_seconds(exc)
        if retry_after is None:
            message = "目前翻譯使用量較多，請稍後再試。"
        else:
            message = f"目前翻譯使用量較多，請在 {retry_after} 秒後再試。"
        return GroqTranslationError(
            message,
            status_code=429,
            retry_after=retry_after,
        )

    @staticmethod
    def _safe_status_error_details(exc: APIStatusError) -> tuple[str, str]:
        """Return diagnostic fields that cannot contain submitted lyric text."""
        body = getattr(exc, "body", None)
        error = body.get("error") if isinstance(body, dict) else None
        if not isinstance(error, dict):
            return "unknown", "unknown"

        error_type = error.get("type")
        error_code = error.get("code")
        return (
            error_type if isinstance(error_type, str) else "unknown",
            error_code if isinstance(error_code, str) else "unknown",
        )

    def regenerate_line(
        self,
        lines: list[ParsedLine],
        target_id: int,
        current_translations: dict[int, str],
        instruction: str = "自然、忠於原意",
    ) -> str:
        source_lines = [line for line in lines if not line.is_blank]
        expected_ids = {line.id for line in source_lines}
        if target_id not in expected_ids:
            raise GroqTranslationError("找不到要重新翻譯的句子，請重新整理後再試。", status_code=400)

        payload = {
            "lines": [{"id": line.id, "text": line.text} for line in source_lines],
            "current_translations": [
                {"id": line.id, "translation": current_translations.get(line.id, "")}
                for line in source_lines
            ],
            "target_id": target_id,
            "instruction": instruction.strip() or "自然、忠於原意",
        }
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "regenerated_line",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "translation": {"type": "string"},
                    },
                    "required": ["id", "translation"],
                    "additionalProperties": False,
                },
            },
        }

        try:
            completion = self._get_client().chat.completions.create(
                model=self._model or os.getenv("GROQ_MODEL", DEFAULT_MODEL),
                messages=[
                    {"role": "system", "content": REGENERATE_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ],
                response_format=response_format,
                reasoning_effort="low",
                temperature=0.45,
                timeout=self._timeout,
            )
        except RateLimitError as exc:
            raise self._rate_limit_error(exc) from exc
        except APITimeoutError as exc:
            raise GroqTranslationError("翻譯等待時間過長，請稍後再試。", status_code=504) from exc
        except APIConnectionError as exc:
            raise GroqTranslationError("暫時無法連線到翻譯服務，請稍後再試。", status_code=503) from exc
        except APIStatusError as exc:
            raise GroqTranslationError("翻譯服務暫時無法使用，請稍後再試。") from exc
        except Exception as exc:
            raise GroqTranslationError("翻譯服務發生問題，請稍後再試。") from exc

        try:
            data = json.loads(completion.choices[0].message.content)
            translation = data.get("translation")
            if (
                type(data.get("id")) is not int
                or data["id"] != target_id
                or not isinstance(translation, str)
                or not translation.strip()
            ):
                raise GroqTranslationError("重新翻譯的結果格式異常，請再試一次。")
            return translation.strip()
        except GroqTranslationError:
            raise
        except (AttributeError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise GroqTranslationError("重新翻譯的結果格式異常，請再試一次。") from exc

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = self._api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise GroqTranslationError("尚未設定 Groq API Key，請先完成環境設定。", status_code=503)
        self._client = self._client_factory(api_key=api_key, max_retries=0)
        return self._client

    @staticmethod
    def _validate_response(data: Any, source_lines: list[ParsedLine]) -> dict[int, str]:
        if not isinstance(data, dict):
            raise GroqTranslationError("翻譯結果格式異常，請重新嘗試。")

        expected_ids = {str(line.id) for line in source_lines}
        if set(data) != expected_ids:
            raise GroqTranslationError("翻譯結果無法與原文對齊，請重新嘗試。")

        translations: dict[int, str] = {}
        for raw_id, translation in data.items():
            if not isinstance(translation, str) or not translation.strip():
                raise GroqTranslationError("翻譯結果格式異常，請重新嘗試。")
            translations[int(raw_id)] = translation.strip()
        return translations

