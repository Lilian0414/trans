from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedLine:
    id: int | None
    text: str
    is_blank: bool


def parse_lyrics(text: str) -> list[ParsedLine]:
    """Normalize outer whitespace while preserving internal paragraph breaks."""
    raw_lines = text.splitlines()
    while raw_lines and not raw_lines[0].strip():
        raw_lines.pop(0)
    while raw_lines and not raw_lines[-1].strip():
        raw_lines.pop()

    parsed: list[ParsedLine] = []
    next_id = 0
    for raw_line in raw_lines:
        normalized = raw_line.strip()
        if not normalized:
            parsed.append(ParsedLine(id=None, text="", is_blank=True))
            continue
        parsed.append(ParsedLine(id=next_id, text=normalized, is_blank=False))
        next_id += 1
    return parsed
