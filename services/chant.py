import re


PRESERVED_CHANT_LINES = {
    "タッタタラリラ",
    "ピーヒャラピーヒャラ",
    "ピーヒャラピー",
    "パッパパラパ",
}

_REPEATED_VOCABLES = ("ラ", "啦", "나", "la", "na", "oh", "ooh", "ah", "ha")
_CHANT_SEPARATORS = re.compile(r"[\s\-‐‑‒–—―]+")


def is_preserved_chant_line(text: str) -> bool:
    """Return true only when the whole line is a recognized rhythmic chant.

    Removing spaces and dash-like separators lets common written variations match,
    while requiring the entire normalized line to be repeated vocables prevents
    ordinary words or mixed lyric lines from being mistaken for chants.
    """
    compact = _CHANT_SEPARATORS.sub("", text.strip()).casefold()
    if not compact:
        return False
    if compact in PRESERVED_CHANT_LINES:
        return True
    for vocable in _REPEATED_VOCABLES:
        count, remainder = divmod(len(compact), len(vocable))
        if remainder == 0 and count >= 3 and compact == vocable * count:
            return True
    return False
