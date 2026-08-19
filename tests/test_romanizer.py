import pytest

from services.numeric_romanizer import romanize_arabic_numbers
from services.romanizer import JapaneseRomanizer


@pytest.fixture(scope="module")
def romanizer() -> JapaneseRomanizer:
    return JapaneseRomanizer()


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("123", "hyaku nijuu san"),
        ("2026年", "nisen nijuu roku nen"),
        ("3月9日", "sangatsu kokonoka"),
        ("1人と20歳", "hitori to hatachi"),
        ("4時10分", "yoji juppun"),
        ("3.14", "san ten ichi yon"),
        ("007", "zero zero nana"),
        ("１２３", "hyaku nijuu san"),
    ],
)
def test_romanizes_arabic_numbers(
    romanizer: JapaneseRomanizer,
    source: str,
    expected: str,
) -> None:
    assert romanizer.romanize_line(source) == expected


def test_number_normalization_does_not_call_an_external_service() -> None:
    normalized = romanize_arabic_numbers("君はNo.1")

    assert normalized == "君はNo. ichi "
    assert "1" not in normalized


def test_very_long_number_falls_back_to_digit_by_digit_reading() -> None:
    source = "1" * 100

    normalized = romanize_arabic_numbers(source)

    assert normalized.split() == ["ichi"] * 100
