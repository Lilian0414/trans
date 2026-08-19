# 日文歌詞翻譯器

一個簡潔的 Flask 網頁：貼上完整日文歌詞後，可選擇 Groq 或 Googletrans 翻成繁體中文，同時透過 `pykakasi` 產生 Hepburn 羅馬字。原文、羅馬字與中文會逐句對齊並保留段落空行；中文結果可直接編輯，也能針對單句取得新的候選翻譯。

## 功能

- Groq：理解完整歌詞上下文，產生較自然的台灣繁體中文。
- Googletrans：不需 API Key 的快速直譯測試選項。
- 逐句編輯：修改後的文字會用於複製與 TXT 下載。
- Groq 單句重翻：可選自然、口語、直譯或文藝風格，先預覽候選版本再決定是否套用。
- Google 參考版本：Groq 結果可逐句取得 Google 候選翻譯並比較。
- 自動草稿：手動修改暫存在目前瀏覽器的 `localStorage`。
- 明確操作回饋：按鈕有按壓、載入、成功與失敗狀態。

## 架構

```text
app.py                       Flask 路由與輸入驗證
services/text_parser.py      保留段落、建立穩定行 ID
services/romanizer.py        日文轉 Hepburn 羅馬字
services/groq_translator.py  單次 Groq structured request 與錯誤處理
services/google_translator.py Googletrans 非官方網頁翻譯介面
services/formatter.py        合併逐句顯示資料
templates/index.html         伺服器端頁面
static/                      編輯器、候選翻譯與複製／下載互動
tests/                       不連網、mock Groq 的測試
```

## 本機執行

需要 Python 3.10 以上。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

將 `.env` 的 `GROQ_API_KEY` 換成自己的 Key，再把環境變數載入並啟動：

```bash
set -a
source .env
set +a
flask --app app run --debug
```

瀏覽 `http://127.0.0.1:5000`。API Key 只由後端環境變數讀取；不要將 `.env` 或真實 Key 提交到 GitHub。

可用 `GROQ_MODEL` 換模型，未設定時預設使用免費測試用的 `openai/gpt-oss-20b`。空白行（包含全形空白）不會送出；純節奏唱詞由程式直接保留原文，其餘歌詞以一次 Groq strict structured output 完成。程式會依本次歌詞 ID 動態建立所有必填 JSON 欄位，從輸出格式上避免漏句、重複 ID 或錯位；不再於同一個 HTTP request 內自動重試或遞迴拆批，避免免費方案的 token 額度被重送的完整歌詞迅速耗盡。遇到 Groq 429 時，頁面會依 `Retry-After` 提示可再次嘗試的時間，伺服器也會回傳正確的 HTTP 429 狀態。單句重新翻譯同樣使用 strict structured output。

## 測試

測試全部 mock Groq 與 Googletrans，不需 API Key 或網路：

```bash
python -m compileall app.py services
pytest
```

## MVP 限制

- 羅馬字由字典式轉換產生，特殊人名或歌詞讀音可能需要人工校正。
- 翻譯品質取決於所選模型，免費方案另有速率限制。
- `googletrans` 使用非官方的 Google Translate 網頁介面，Google 改版或限制 Vercel IP 時可能暫時失效；程式會顯示友善錯誤，不影響 Groq 選項。
- 本版不包含帳號、翻譯紀錄、資料庫或自動抓取歌詞。

