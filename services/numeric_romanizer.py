import re


_DIGIT_READINGS = (
    "zero",
    "ichi",
    "ni",
    "san",
    "yon",
    "go",
    "roku",
    "nana",
    "hachi",
    "kyuu",
)

_LARGE_UNITS = ("", "man", "oku", "chou", "kei")
_MAX_STRUCTURED_DIGITS = len(_LARGE_UNITS) * 4

_COUNTER_PATTERN = re.compile(
    r"(?P<number>\d(?:[\d,]*\d)?)"
    r"(?P<counter>ヶ月|か月|カ月|日間|時間|分間|秒間|週間|月|日|人|時|分|秒|年|歳|才|回|個|本|匹|枚|台|番|円|度|%)"
)
_NUMBER_PATTERN = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d+")

_MONTH_READINGS = {
    1: "ichigatsu",
    2: "nigatsu",
    3: "sangatsu",
    4: "shigatsu",
    5: "gogatsu",
    6: "rokugatsu",
    7: "shichigatsu",
    8: "hachigatsu",
    9: "kugatsu",
    10: "juugatsu",
    11: "juuichigatsu",
    12: "juunigatsu",
}

_DAY_READINGS = {
    1: "tsuitachi",
    2: "futsuka",
    3: "mikka",
    4: "yokka",
    5: "itsuka",
    6: "muika",
    7: "nanoka",
    8: "youka",
    9: "kokonoka",
    10: "tooka",
    14: "juuyokka",
    20: "hatsuka",
    24: "nijuuyokka",
}

_HOUR_READINGS = {
    1: "ichiji",
    2: "niji",
    3: "sanji",
    4: "yoji",
    5: "goji",
    6: "rokuji",
    7: "shichiji",
    8: "hachiji",
    9: "kuji",
    10: "juuji",
}

_MINUTE_READINGS = {
    1: "ippun",
    2: "nifun",
    3: "sanpun",
    4: "yonpun",
    5: "gofun",
    6: "roppun",
    7: "nanafun",
    8: "happun",
    9: "kyuufun",
    10: "juppun",
}


def _read_under_10_000(number: int) -> list[str]:
    readings: list[str] = []

    thousands, number = divmod(number, 1_000)
    if thousands:
        readings.append(
            {1: "sen", 3: "sanzen", 8: "hassen"}.get(
                thousands, f"{_DIGIT_READINGS[thousands]}sen"
            )
        )

    hundreds, number = divmod(number, 100)
    if hundreds:
        readings.append(
            {1: "hyaku", 3: "sanbyaku", 6: "roppyaku", 8: "happyaku"}.get(
                hundreds, f"{_DIGIT_READINGS[hundreds]}hyaku"
            )
        )

    tens, ones = divmod(number, 10)
    if tens:
        readings.append("juu" if tens == 1 else f"{_DIGIT_READINGS[tens]}juu")
    if ones:
        readings.append(_DIGIT_READINGS[ones])

    return readings


def _read_integer(number: int) -> str:
    if number == 0:
        return _DIGIT_READINGS[0]

    chunks: list[tuple[int, int]] = []
    unit_index = 0
    remaining = number
    while remaining:
        remaining, chunk = divmod(remaining, 10_000)
        if chunk:
            chunks.append((chunk, unit_index))
        unit_index += 1

    if any(index >= len(_LARGE_UNITS) for _, index in chunks):
        return " ".join(_DIGIT_READINGS[int(digit)] for digit in str(number))

    readings: list[str] = []
    for chunk, index in reversed(chunks):
        chunk_reading = _read_under_10_000(chunk)
        unit = _LARGE_UNITS[index]
        if unit:
            readings.append("".join(chunk_reading) + unit)
        else:
            readings.extend(chunk_reading)
    return " ".join(readings)


def _read_literal(raw_number: str) -> str:
    normalized = raw_number.replace(",", "")
    if "." in normalized:
        whole, fraction = normalized.split(".", 1)
        whole_reading = _read_literal(whole or "0")
        fraction_reading = " ".join(_DIGIT_READINGS[int(digit)] for digit in fraction)
        return f"{whole_reading} ten {fraction_reading}"

    if len(normalized) > _MAX_STRUCTURED_DIGITS:
        return " ".join(_DIGIT_READINGS[int(digit)] for digit in normalized)
    if len(normalized) > 1 and normalized.startswith("0"):
        return " ".join(_DIGIT_READINGS[int(digit)] for digit in normalized)
    return _read_integer(int(normalized))


def _read_with_last_form(number: int, forms: dict[int, str], suffix: str) -> str:
    if number in forms:
        return forms[number]
    if 10 < number < 100:
        last_digit = number % 10
        if last_digit in forms:
            prefix = _read_integer(number - last_digit)
            return f"{prefix} {forms[last_digit]}"
        if last_digit == 0 and 10 in forms:
            prefix = "" if number == 10 else _read_integer(number // 10)
            return f"{prefix}{forms[10]}"
    return f"{_read_integer(number)} {suffix}"


def _read_counter(raw_number: str, counter: str) -> str:
    normalized_number = raw_number.replace(",", "")
    if len(normalized_number) > _MAX_STRUCTURED_DIGITS:
        suffixes = {
            "ヶ月": "kagetsu",
            "か月": "kagetsu",
            "カ月": "kagetsu",
            "日間": "nichikan",
            "時間": "jikan",
            "分間": "funkan",
            "秒間": "byoukan",
            "週間": "shuukan",
            "月": "gatsu",
            "日": "nichi",
            "人": "nin",
            "時": "ji",
            "分": "fun",
            "秒": "byou",
            "年": "nen",
            "歳": "sai",
            "才": "sai",
            "回": "kai",
            "個": "ko",
            "本": "hon",
            "匹": "hiki",
            "枚": "mai",
            "台": "dai",
            "番": "ban",
            "円": "en",
            "度": "do",
            "%": "paasento",
        }
        return f"{_read_literal(normalized_number)} {suffixes[counter]}"

    number = int(normalized_number)

    if counter == "月":
        return _MONTH_READINGS.get(number, f"{_read_integer(number)} gatsu")
    if counter == "日":
        return _DAY_READINGS.get(number, f"{_read_integer(number)} nichi")
    if counter == "日間":
        if number == 1:
            return "ichinichikan"
        day = _DAY_READINGS.get(number, f"{_read_integer(number)} nichi")
        return f"{day}kan"
    if counter == "人":
        if number == 1:
            return "hitori"
        if number == 2:
            return "futari"
        return f"{_read_integer(number)} nin"
    if counter == "時":
        return _read_with_last_form(number, _HOUR_READINGS, "ji")
    if counter == "時間":
        return f"{_read_integer(number)} jikan"
    if counter in {"分", "分間"}:
        minute = _read_with_last_form(number, _MINUTE_READINGS, "fun")
        return f"{minute}kan" if counter == "分間" else minute
    if counter in {"秒", "秒間"}:
        second = f"{_read_integer(number)} byou"
        return f"{second}kan" if counter == "秒間" else second
    if counter == "週間":
        if number == 1:
            return "isshuukan"
        return f"{_read_integer(number)} shuukan"
    if counter in {"歳", "才"}:
        if number == 20:
            return "hatachi"
        return _read_with_last_form(
            number,
            {1: "issai", 8: "hassai", 10: "jussai"},
            "sai",
        )
    if counter == "回":
        return _read_with_last_form(
            number,
            {1: "ikkai", 6: "rokkai", 8: "hakkai", 10: "jukkai"},
            "kai",
        )
    if counter == "個":
        return _read_with_last_form(
            number,
            {1: "ikko", 6: "rokko", 8: "hakko", 10: "jukko"},
            "ko",
        )
    if counter == "本":
        return _read_with_last_form(
            number,
            {1: "ippon", 3: "sanbon", 6: "roppon", 8: "happon", 10: "juppon"},
            "hon",
        )
    if counter == "匹":
        return _read_with_last_form(
            number,
            {1: "ippiki", 3: "sanbiki", 6: "roppiki", 8: "happiki", 10: "juppiki"},
            "hiki",
        )

    suffixes = {
        "ヶ月": "kagetsu",
        "か月": "kagetsu",
        "カ月": "kagetsu",
        "年": "nen",
        "枚": "mai",
        "台": "dai",
        "番": "ban",
        "円": "en",
        "度": "do",
        "%": "paasento",
    }
    return f"{_read_integer(number)} {suffixes[counter]}"


def romanize_arabic_numbers(text: str) -> str:
    """Replace Arabic numerals with local Hepburn readings before pykakasi runs."""

    normalized = text.translate(str.maketrans("０１２３４５６７８９，．％", "0123456789,.%"))
    normalized = _COUNTER_PATTERN.sub(
        lambda match: f" {_read_counter(match.group('number'), match.group('counter'))} ",
        normalized,
    )
    return _NUMBER_PATTERN.sub(lambda match: f" {_read_literal(match.group(0))} ", normalized)
