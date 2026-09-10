import pytest

from services.chant import is_preserved_chant_line


@pytest.mark.parametrize(
    "text",
    [
        "ラララ",
        "ラ ラ ラ",
        "啦啦啦",
        "나 나 나",
        "la la la",
        "oh-oh-oh",
        "タッタタラリラ",
        "ピーヒャラピーヒャラ",
        "ピーヒャラピー",
        "パッパパラパ",
    ],
)
def test_whole_line_chants_are_preserved(text):
    assert is_preserved_chant_line(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "language",
        "landscape",
        "natural",
        "la vie en rose",
        "Oh 君が好き",
        "ラララと歌う",
    ],
)
def test_semantic_or_mixed_lines_are_not_preserved(text):
    assert is_preserved_chant_line(text) is False
