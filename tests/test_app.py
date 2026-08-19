import app as app_module
from services.groq_translator import GroqTranslationError


class FakeTranslator:
    def __init__(self, result=None, error=None, regenerated="新的翻譯"):
        self.result = result or {}
        self.error = error
        self.regenerated = regenerated
        self.calls = 0
        self.regenerate_calls = []

    def translate(self, lines):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result

    def regenerate_line(self, lines, target_id, translations, instruction):
        self.regenerate_calls.append((lines, target_id, translations, instruction))
        if self.error:
            raise self.error
        return self.regenerated

    def translate_line(self, text):
        if self.error:
            raise self.error
        return self.regenerated


class FakeRomanizer:
    def romanize_line(self, text):
        return "kimi" if text == "君" else "yoru"


def test_get_works_without_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert app_module.app.test_client().get("/").status_code == 200


def test_blank_post_does_not_call_translator(monkeypatch):
    fake = FakeTranslator()
    monkeypatch.setattr(app_module, "groq_translator", fake)
    response = app_module.app.test_client().post("/", data={"lyrics": "  \n"})
    assert response.status_code == 200
    assert fake.calls == 0
    assert "請先貼上" in response.get_data(as_text=True)
    assert 'id="form-error"' in response.get_data(as_text=True)


def test_success_post_renders_aligned_results(monkeypatch):
    monkeypatch.setattr(app_module, "groq_translator", FakeTranslator({0: "你", 1: "夜晚"}))
    monkeypatch.setattr(app_module, "romanizer", FakeRomanizer())
    response = app_module.app.test_client().post("/", data={"lyrics": "君\n\n夜"})
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "kimi" in body and "你" in body and "夜晚" in body
    assert 'class="paragraph-break"' in body
    assert 'class="translation-editor"' in body
    assert 'data-line-id="0"' in body


def test_service_error_is_friendly_and_sanitized(monkeypatch):
    private_detail = "internal-request-secret"
    fake = FakeTranslator(
        error=GroqTranslationError(
            "目前翻譯使用量較多，請在 8 秒後再試。",
            status_code=429,
            retry_after=8,
        )
    )
    monkeypatch.setattr(app_module, "groq_translator", fake)
    response = app_module.app.test_client().post("/", data={"lyrics": "君"})
    body = response.get_data(as_text=True)
    assert "目前翻譯使用量較多" in body
    assert private_detail not in body
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "8"


def test_clear_interaction_has_reset_targets():
    with open("static/app.js", encoding="utf-8") as script_file:
        script = script_file.read()

    assert 'querySelector("#form-error")?.remove()' in script
    assert 'querySelector("#results")?.remove()' in script
    assert "submitButton.disabled = false" in script
    assert 'querySelector(".button-label").hidden = false' in script
    assert 'querySelector(".loading-label").hidden = true' in script
    assert '"\\n".repeat(2 + preservedBlankLines)' in script
    assert 'querySelector(".translation-editor").value' in script
    assert 'flashButton(button, "✓ 已複製")' in script


def test_google_provider_is_selectable_for_full_translation(monkeypatch):
    fake_google = FakeTranslator({0: "Google 版本"})
    monkeypatch.setattr(app_module, "google_translator", fake_google)
    monkeypatch.setattr(app_module, "romanizer", FakeRomanizer())
    response = app_module.app.test_client().post(
        "/", data={"lyrics": "君", "provider": "google"}
    )
    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Google 版本" in body
    assert 'value="google" checked' in body


def test_regenerate_line_api_returns_candidate_without_overwriting(monkeypatch):
    fake = FakeTranslator(regenerated="即使如此，我仍想見你")
    monkeypatch.setattr(app_module, "groq_translator", fake)
    response = app_module.app.test_client().post(
        "/api/regenerate-line",
        json={
            "lyrics": "それでも\n君に会いたい",
            "target_id": 1,
            "translations": {"0": "即使如此", "1": "想見你"},
            "instruction": "更自然",
        },
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "translation": "即使如此，我仍想見你",
        "provider": "groq",
    }
    assert fake.regenerate_calls[0][1:] == (
        1,
        {0: "即使如此", 1: "想見你"},
        "更自然",
    )


def test_regenerate_line_api_propagates_rate_limit(monkeypatch):
    fake = FakeTranslator(
        error=GroqTranslationError(
            "目前翻譯使用量較多，請在 5 秒後再試。",
            status_code=429,
            retry_after=5,
        )
    )
    monkeypatch.setattr(app_module, "groq_translator", fake)

    response = app_module.app.test_client().post(
        "/api/regenerate-line",
        json={"lyrics": "君", "target_id": 0, "translations": {}},
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "5"
    assert "5 秒後" in response.get_json()["error"]


def test_line_apis_reject_unknown_target():
    response = app_module.app.test_client().post(
        "/api/regenerate-line",
        json={"lyrics": "君", "target_id": 9, "translations": {}},
    )
    assert response.status_code == 400
    assert "找不到" in response.get_json()["error"]


def test_google_line_api_returns_reference_candidate(monkeypatch):
    fake_google = FakeTranslator(regenerated="我想見你")
    monkeypatch.setattr(app_module, "google_translator", fake_google)
    response = app_module.app.test_client().post(
        "/api/google-line", json={"lyrics": "君に会いたい", "target_id": 0}
    )
    assert response.status_code == 200
    assert response.get_json() == {"translation": "我想見你", "provider": "google"}
