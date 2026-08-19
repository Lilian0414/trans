from dataclasses import dataclass
from typing import Mapping, Protocol

from services.text_parser import ParsedLine


class Romanizer(Protocol):
    def romanize_line(self, text: str) -> str: ...


@dataclass(frozen=True)
class LineResult:
    id: int | None
    original: str
    romaji: str
    chinese: str
    is_blank: bool = False


class LyricsFormatter:
    """Combine parsed lyrics, romaji, and translations without losing alignment."""

    @staticmethod
    def build(
        lines: list[ParsedLine],
        translations: Mapping[int, str],
        romanizer: Romanizer,
    ) -> list[LineResult]:
        results: list[LineResult] = []
        for line in lines:
            if line.is_blank:
                results.append(LineResult(None, "", "", "", is_blank=True))
                continue
            assert line.id is not None
            results.append(
                LineResult(
                    id=line.id,
                    original=line.text,
                    romaji=romanizer.romanize_line(line.text),
                    chinese=translations[line.id],
                )
            )
        return results
