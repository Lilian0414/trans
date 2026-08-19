from pykakasi import kakasi

from services.numeric_romanizer import romanize_arabic_numbers


class JapaneseRomanizer:
    """Convert one Japanese lyric line to Hepburn romaji."""

    def __init__(self) -> None:
        self._converter = kakasi()

    def romanize_line(self, text: str) -> str:
        if not text.strip():
            return ""
        parts = self._converter.convert(romanize_arabic_numbers(text))
        romaji = " ".join(part["hepburn"] for part in parts)
        return " ".join(romaji.split())
