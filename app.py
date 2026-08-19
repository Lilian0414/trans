from flask import Flask, jsonify, make_response, render_template, request

from services.formatter import LyricsFormatter
from services.google_translator import GoogleTranslationError, GoogleTransTranslator
from services.groq_translator import GroqTranslationError, GroqTranslator
from services.romanizer import JapaneseRomanizer
from services.text_parser import ParsedLine, parse_lyrics

MAX_LYRICS_LENGTH = 12_000
MAX_INSTRUCTION_LENGTH = 300
SUPPORTED_PROVIDERS = {"groq", "google"}

app = Flask(__name__)

romanizer = JapaneseRomanizer()
groq_translator = GroqTranslator()
google_translator = GoogleTransTranslator()


@app.route("/", methods=["GET", "POST"])
def index():
    input_lyrics = ""
    results = None
    error = None
    status_code = 200
    retry_after = None
    provider = "groq"

    if request.method == "POST":
        input_lyrics = request.form.get("lyrics", "")
        provider = request.form.get("provider", "groq")
        if not input_lyrics.strip():
            error = "請先貼上要翻譯的日文歌詞。"
        elif len(input_lyrics) > MAX_LYRICS_LENGTH:
            error = f"歌詞最多可輸入 {MAX_LYRICS_LENGTH:,} 個字元，請縮短後再試。"
        elif provider not in SUPPORTED_PROVIDERS:
            error = "不支援這個翻譯引擎，請重新選擇。"
        else:
            parsed_lines = parse_lyrics(input_lyrics)
            try:
                active_translator = google_translator if provider == "google" else groq_translator
                translations = active_translator.translate(parsed_lines)
                results = LyricsFormatter.build(parsed_lines, translations, romanizer)
            except GroqTranslationError as exc:
                error = exc.user_message
                status_code = exc.status_code
                retry_after = exc.retry_after
            except GoogleTranslationError as exc:
                error = exc.user_message
                status_code = 502

    response = make_response(
        render_template(
            "index.html",
            input_lyrics=input_lyrics,
            results=results,
            error=error,
            max_length=MAX_LYRICS_LENGTH,
            provider=provider,
        ),
        status_code,
    )
    if retry_after is not None:
        response.headers["Retry-After"] = str(retry_after)
    return response


def _validated_target(payload: object) -> tuple[list[ParsedLine], int]:
    if not isinstance(payload, dict):
        raise ValueError("請求格式不正確，請重新整理後再試。")
    lyrics = payload.get("lyrics")
    target_id = payload.get("target_id")
    if not isinstance(lyrics, str) or not lyrics.strip():
        raise ValueError("找不到原始歌詞，請重新整理後再試。")
    if len(lyrics) > MAX_LYRICS_LENGTH:
        raise ValueError(f"歌詞最多可輸入 {MAX_LYRICS_LENGTH:,} 個字元。")
    if type(target_id) is not int:
        raise ValueError("找不到要翻譯的句子，請重新整理後再試。")

    parsed_lines = parse_lyrics(lyrics)
    valid_ids = {line.id for line in parsed_lines if not line.is_blank}
    if target_id not in valid_ids:
        raise ValueError("找不到要翻譯的句子，請重新整理後再試。")
    return parsed_lines, target_id


@app.post("/api/regenerate-line")
def regenerate_line():
    payload = request.get_json(silent=True)
    try:
        parsed_lines, target_id = _validated_target(payload)
        assert isinstance(payload, dict)
        instruction = payload.get("instruction", "自然、忠於原意")
        if not isinstance(instruction, str) or len(instruction) > MAX_INSTRUCTION_LENGTH:
            raise ValueError(f"翻譯要求最多 {MAX_INSTRUCTION_LENGTH} 個字元。")

        raw_translations = payload.get("translations", {})
        if not isinstance(raw_translations, dict):
            raise ValueError("目前譯文格式不正確，請重新整理後再試。")
        valid_ids = {line.id for line in parsed_lines if not line.is_blank}
        current_translations: dict[int, str] = {}
        for raw_id, translation in raw_translations.items():
            try:
                line_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if line_id in valid_ids and isinstance(translation, str):
                current_translations[line_id] = translation[:4_000]

        translation = groq_translator.regenerate_line(
            parsed_lines,
            target_id,
            current_translations,
            instruction,
        )
        return jsonify({"translation": translation, "provider": "groq"})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except GroqTranslationError as exc:
        response = jsonify({"error": exc.user_message})
        response.status_code = exc.status_code
        if exc.retry_after is not None:
            response.headers["Retry-After"] = str(exc.retry_after)
        return response


@app.post("/api/google-line")
def google_line():
    payload = request.get_json(silent=True)
    try:
        parsed_lines, target_id = _validated_target(payload)
        target = next(line for line in parsed_lines if line.id == target_id)
        translation = google_translator.translate_line(target.text)
        return jsonify({"translation": translation, "provider": "google"})
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except GoogleTranslationError as exc:
        return jsonify({"error": exc.user_message}), 502


if __name__ == "__main__":
    app.run(debug=True)
