const DRAFT_STORAGE_KEY = "trans-translation-draft-v1";
const form = document.querySelector("#lyrics-form");
const textarea = document.querySelector("#lyrics");
const submitButton = document.querySelector("#submit-button");
const feedbackTimers = new WeakMap();

form?.addEventListener("submit", () => {
  try {
    localStorage.removeItem(DRAFT_STORAGE_KEY);
  } catch {
    // Storage is optional; translation still works when the browser blocks it.
  }
  submitButton.disabled = true;
  submitButton.setAttribute("aria-busy", "true");
  submitButton.querySelector(".button-label").hidden = true;
  submitButton.querySelector(".loading-label").hidden = false;
});

document.querySelector("#clear-button")?.addEventListener("click", (event) => {
  textarea.value = "";
  document.querySelector("#interaction-status")?.replaceChildren();
  document.querySelector("#form-error")?.remove();
  document.querySelector("#results")?.remove();
  submitButton.disabled = false;
  submitButton.removeAttribute("aria-busy");
  submitButton.querySelector(".button-label").hidden = false;
  submitButton.querySelector(".loading-label").hidden = true;
  try {
    localStorage.removeItem(DRAFT_STORAGE_KEY);
  } catch {
    // Ignore unavailable browser storage.
  }
  flashButton(event.currentTarget, "已清空");
  textarea.focus();
});

function lyricLines() {
  return [...document.querySelectorAll("#lyrics-output .lyric-line")];
}

function currentTranslation(article) {
  return article.querySelector(".translation-editor").value.trim();
}

function collectTranslations() {
  return Object.fromEntries(
    lyricLines().map((article) => [article.dataset.lineId, currentTranslation(article)]),
  );
}

function buildSourceLyrics() {
  return [...document.querySelectorAll("#lyrics-output > *")]
    .map((element) => element.classList.contains("paragraph-break") ? "" : element.dataset.original)
    .join("\n");
}

function buildPlainText() {
  let output = "";
  let preservedBlankLines = 0;

  for (const element of document.querySelectorAll("#lyrics-output > *")) {
    if (element.classList.contains("paragraph-break")) {
      preservedBlankLines += 1;
      continue;
    }

    if (output) output += "\n".repeat(2 + preservedBlankLines);
    output += [element.dataset.original, element.dataset.romaji, currentTranslation(element)].join("\n");
    preservedBlankLines = 0;
  }

  return output;
}

function setStatus(message, type = "") {
  const status = document.querySelector("#interaction-status");
  if (!status) return;
  status.textContent = message;
  status.className = `status ${type}`.trim();
}

function setLineStatus(article, message, type = "") {
  const status = article.querySelector(".line-status");
  status.textContent = message;
  status.className = `line-status ${type}`.trim();
}

function flashButton(button, temporaryLabel, type = "success", duration = 1600) {
  if (!button) return;
  const idleLabel = button.dataset.idleLabel || button.textContent.trim();
  button.dataset.idleLabel = idleLabel;
  button.textContent = temporaryLabel;
  button.classList.remove("feedback-success", "feedback-error");
  button.classList.add(type === "error" ? "feedback-error" : "feedback-success");
  clearTimeout(feedbackTimers.get(button));
  feedbackTimers.set(
    button,
    setTimeout(() => {
      button.textContent = idleLabel;
      button.classList.remove("feedback-success", "feedback-error");
    }, duration),
  );
}

function setButtonLoading(button, loading, loadingLabel = "處理中…") {
  if (loading) {
    button.dataset.idleLabel = button.textContent.trim();
    button.textContent = loadingLabel;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
  } else {
    button.textContent = button.dataset.idleLabel;
    button.disabled = false;
    button.removeAttribute("aria-busy");
  }
}

function updateProviderBadge(article, provider) {
  article.dataset.provider = provider;
  const badge = article.querySelector(".provider-badge");
  badge.textContent = provider === "google" ? "Google" : "Groq";
  badge.className = `provider-badge ${provider}`;
}

function updateEditedState(article) {
  const isEdited = currentTranslation(article) !== article.dataset.initialTranslation;
  article.querySelector(".edited-badge").hidden = !isEdited;
  article.classList.toggle("is-edited", isEdited);
}

function saveDraft() {
  if (!textarea || !lyricLines().length) return;
  const lines = Object.fromEntries(
    lyricLines().map((article) => [
      article.dataset.lineId,
      { text: article.querySelector(".translation-editor").value, provider: article.dataset.provider },
    ]),
  );
  try {
    localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify({ lyrics: textarea.value, lines }));
  } catch {
    // Draft saving is a convenience, not a requirement for editing.
  }
}

function restoreDraft() {
  try {
    const draft = JSON.parse(localStorage.getItem(DRAFT_STORAGE_KEY));
    if (!draft || draft.lyrics !== textarea?.value || typeof draft.lines !== "object") return;
    for (const article of lyricLines()) {
      const saved = draft.lines[article.dataset.lineId];
      if (!saved || typeof saved.text !== "string") continue;
      article.querySelector(".translation-editor").value = saved.text;
      if (saved.provider === "groq" || saved.provider === "google") {
        updateProviderBadge(article, saved.provider);
      }
      updateEditedState(article);
    }
    setStatus("已恢復上次尚未完成的修改。", "success");
  } catch {
    // Ignore malformed or unavailable storage.
  }
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "服務暫時沒有回應，請稍後再試。");
  return data;
}

for (const article of lyricLines()) {
  article.dataset.initialProvider = article.dataset.provider;
  const editor = article.querySelector(".translation-editor");

  editor.addEventListener("input", () => {
    updateEditedState(article);
    saveDraft();
    setLineStatus(article, "已儲存在這台裝置的瀏覽器中。", "success");
  });

  article.querySelector(".reset-line-button").addEventListener("click", (event) => {
    editor.value = article.dataset.initialTranslation;
    updateProviderBadge(article, article.dataset.initialProvider);
    updateEditedState(article);
    article.querySelectorAll(".candidate-panel").forEach((panel) => { panel.hidden = true; });
    saveDraft();
    setLineStatus(article, "已還原這一句。", "success");
    flashButton(event.currentTarget, "✓ 已還原");
  });

  article.querySelector(".regenerate-button").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const style = article.querySelector(".style-select").value;
    const custom = article.querySelector(".custom-instruction").value.trim();
    const instruction = custom ? `${style}；補充要求：${custom}` : style;
    let feedbackLabel = "✓ 已產生";
    let feedbackType = "success";
    setButtonLoading(button, true, "Groq 生成中…");
    setLineStatus(article, "正在參考完整歌詞重新翻譯這一句…");
    try {
      const data = await postJson("/api/regenerate-line", {
        lyrics: buildSourceLyrics(),
        target_id: Number(article.dataset.lineId),
        translations: collectTranslations(),
        instruction,
      });
      const panel = article.querySelector(".groq-candidate");
      panel.querySelector(".candidate-text").textContent = data.translation;
      panel.hidden = false;
      setLineStatus(article, "Groq 候選版本已產生，確認後再套用。", "success");
    } catch (error) {
      setLineStatus(article, error.message, "error");
      feedbackLabel = "重試";
      feedbackType = "error";
    } finally {
      setButtonLoading(button, false);
      flashButton(button, feedbackLabel, feedbackType);
    }
  });

  article.querySelector(".google-button")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    let feedbackLabel = "✓ 已取得";
    let feedbackType = "success";
    setButtonLoading(button, true, "Google 翻譯中…");
    setLineStatus(article, "正在取得 Google 參考版本…");
    try {
      const data = await postJson("/api/google-line", {
        lyrics: buildSourceLyrics(),
        target_id: Number(article.dataset.lineId),
      });
      const panel = article.querySelector(".google-candidate");
      panel.querySelector(".candidate-text").textContent = data.translation;
      panel.hidden = false;
      setLineStatus(article, "Google 參考版本已取得，確認後再套用。", "success");
    } catch (error) {
      setLineStatus(article, error.message, "error");
      feedbackLabel = "重試";
      feedbackType = "error";
    } finally {
      setButtonLoading(button, false);
      flashButton(button, feedbackLabel, feedbackType);
    }
  });

  for (const panel of article.querySelectorAll(".candidate-panel")) {
    panel.querySelector(".apply-candidate").addEventListener("click", (event) => {
      editor.value = panel.querySelector(".candidate-text").textContent;
      updateProviderBadge(article, panel.classList.contains("google-candidate") ? "google" : "groq");
      updateEditedState(article);
      panel.hidden = true;
      saveDraft();
      setLineStatus(article, "已套用候選翻譯。", "success");
      flashButton(event.currentTarget, "✓ 已套用");
    });
    panel.querySelector(".dismiss-candidate").addEventListener("click", (event) => {
      panel.hidden = true;
      setLineStatus(article, "已保留目前的翻譯。", "success");
      flashButton(event.currentTarget, "✓ 已保留");
    });
  }
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const helper = document.createElement("textarea");
  helper.value = text;
  helper.setAttribute("readonly", "");
  helper.className = "clipboard-helper";
  document.body.appendChild(helper);
  helper.select();
  const copied = document.execCommand("copy");
  helper.remove();
  if (!copied) throw new Error("copy failed");
}

document.querySelector("#copy-button")?.addEventListener("click", async (event) => {
  const button = event.currentTarget;
  try {
    await copyText(buildPlainText());
    setStatus("✓ 已複製目前編輯的完整結果。", "success");
    flashButton(button, "✓ 已複製");
  } catch {
    setStatus("無法自動複製，請手動選取內容。", "error");
    flashButton(button, "複製失敗", "error");
  }
});

document.querySelector("#download-button")?.addEventListener("click", (event) => {
  const blob = new Blob([buildPlainText()], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "日文歌詞翻譯.txt";
  link.click();
  URL.revokeObjectURL(link.href);
  setStatus("✓ 下載已開始，內容包含目前所有修改。", "success");
  flashButton(event.currentTarget, "✓ 下載中");
});

restoreDraft();
