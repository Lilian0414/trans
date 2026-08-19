from services.formatter import LyricsFormatter
from services.text_parser import parse_lyrics


class FakeRomanizer:
    def romanize_line(self, text):
        return f"ROMAJI:{text}"


def test_formatter_aligns_all_fields_and_blank_lines():
    result = LyricsFormatter.build(parse_lyrics("君\n\n夜"), {0: "你", 1: "夜晚"}, FakeRomanizer())
    assert result[0].id == 0
    assert result[0].original == "君"
    assert result[0].romaji == "ROMAJI:君"
    assert result[0].chinese == "你"
    assert result[1].is_blank is True
    assert result[1].id is None
    assert result[2].chinese == "夜晚"
