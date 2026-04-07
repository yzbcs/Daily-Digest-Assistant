# 📬 Daily Digest Assistant

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green" alt="License" /></a>
  <a href="#-supported-llm-providers"><img src="https://img.shields.io/badge/LLM-MiniMax%20%7C%20Claude%20%7C%20OpenAI-orange" alt="LLM" /></a>
  <a href="https://github.com/yzbcs/Daily-Digest-Assistant/actions"><img src="https://img.shields.io/badge/Deploy-GitHub%20Actions-black?logo=github" alt="Deploy" /></a>
</p>

<p align="center">
  <b>Every day at noon, get精选 arXiv papers and Xiaohongshu notes delivered to your inbox.</b><br/>
  LLM-powered filtering + Chinese summaries + detailed breakdowns, fork and go, no server needed.
</p>

<p align="center">

[🇨 中文版](./README.md)

</p>

---

## 📸 Preview

The email uses a **side-by-side two-column layout** — arXiv papers on the left, Xiaohongshu notes on the right:

- **arXiv Papers**: one-line summary + detailed breakdown + PDF link; shows "We're resting today~" on holidays/weekends
- **Xiaohongshu Notes**: content summary + link; updated daily (unaffected by arXiv holidays)

---

## ✨ Features

- 🔍 **Accurate timing**: fetches by arXiv's official announcement batches — no misses, no duplicates
- 🤖 **LLM smart filtering**: selects the most relevant Top 10 from candidates, low-relevance papers are dropped
- 🈶 **Dual-layer Chinese summary**: one-line summary + 100-150 character detailed breakdown
- 📬 **HTML email**: beautiful card layout with **side-by-side columns** for arXiv / Xiaohongshu
- 📕 **Xiaohongshu sync**: daily keyword search + LLM filtering, runs every day (not affected by arXiv holidays)
- 🔄 **Deduplication**: tracks sent papers, never sends the same one twice
- 🧩 **Multi-LLM support**: Claude / MiniMax / OpenAI / DeepSeek / Zhipu / Kimi / Qwen — switch with one line
- ⚙️ **Zero-server deployment**: fully powered by GitHub Actions, free and automatic

---

## 🚀 Quick Start (5 min)

### Step 1: Fork This Repo

Click **Fork** in the top-right corner to copy the repo to your GitHub account.

### Step 2: Edit Keywords + Install Dependencies

Edit `config.yml` with your keywords and categories (other settings can stay as-is).
You can also edit files directly on the GitHub website — no need to clone locally!

```yaml
keywords:
  - agent          # multiple keywords supported — match any one to enter candidate pool
  - skill
  - your_keyword

categories:        # leave empty to search all categories
  - cs.AI
  - cs.LG
```

Then install Python and Node.js dependencies if running locally:

```bash
pip install -r requirements.txt
npm install
```

> GitHub Actions installs Node.js dependencies automatically — only needed for local runs.

### Step 3: Configure GitHub Secrets

Go to your fork → **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret Name | Description |
|------------|-------------|
| `LLM_API_KEY` | LLM API Key |
| `EMAIL_USER` | Sender email address (163 / Gmail / QQ) |
| `EMAIL_PASS` | Sender **authorization code** (not your login password, see below) |
| `EMAIL_TO` | Recipient email address |
| `XHS_COOKIE` | Xiaohongshu web Cookie (optional — skip if not needed) ⚠️ Cookie expires ~every 30 days, needs periodic renewal |

### Step 4: Run Once to Verify

Go to **Actions → Daily Paper Digest → Run workflow**, trigger it manually, and check your inbox.

After that, it runs automatically every day at **12:00 Beijing time** (arXiv holidays Fri/Sat still push Xiaohongshu content).

---

## 📮 Email Authorization Code

> Authorization code ≠ login password — it's a separate password for third-party clients.

- **163 mail**: Web → Settings → POP3/SMTP/IMAP → Enable SMTP → Generate authorization code
- **Gmail**: Enable 2FA → Security → App passwords → Generate
- **QQ mail**: Settings → Account → Enable SMTP → Get authorization code

---

## 🔧 Supported LLM Providers

Change `llm_provider` in `config.yml`:

| provider | Service | Notes |
|----------|---------|-------|
| `minimax` | MiniMax M2.7 | Default, strong reasoning |
| `claude` | Anthropic Claude Haiku | Fast, stable output |
| `openai` | OpenAI GPT-4o mini | General purpose |
| `deepseek` | DeepSeek | Fast in China, great value |
| `zhipu` | Zhipu GLM | China fallback |
| `moonshot` | Moonshot Kimi | China fallback |
| `qwen` | Alibaba Qwen | China fallback |

> Adding a new provider only requires one line in `llm/filter_and_summarize.py`'s `PROVIDER_REGISTRY`.

---

## ⚙️ Full Config Reference

All options in `config.yml`:

```yaml
# Paper keywords (OR — match any one to enter candidate pool)
keywords:
  - agent
  - skill
  - openclaw

# arXiv category filter (leave empty for all categories)
# Common: cs.AI cs.LG cs.RO cs.CL cs.CV
categories:
  - cs.AI
  - cs.LG
  - cs.RO

# Max papers to send per day
max_papers: 10

# LLM relevance threshold (1-10) — papers below this are dropped
# Higher (e.g. 8) → stricter, fewer but more relevant
# Lower (e.g. 4) → looser, more results
min_score: 5

# Candidate pool size: search this many, then LLM filters down to max_papers
candidate_pool: 50

# Email provider
smtp_provider: "163"   # 163 / gmail / qq

# LLM provider
llm_provider: minimax  # minimax / claude / openai / deepseek / zhipu / moonshot / qwen

# ── Xiaohongshu Config ───────────────────────────────────────
# Leave empty to reuse keywords above; set custom search terms here
xhs_keywords: []

# Initial candidate pool size for Xiaohongshu (default 30 if empty)
xhs_candidate_pool: 30
```

---

## 💻 Local Run / Test

```bash
git clone https://github.com/yzbcs/Arxiv-Daily-Digest.git
cd Arxiv-Daily-Digest
pip install -r requirements.txt
npm install

export LLM_API_KEY="your_api_key"
export EMAIL_USER="xxx@163.com"       # optional, 163/gmail/qq
export EMAIL_PASS="your_smtp_password"
export EMAIL_TO="xxx@qq.com"          # optional
export XHS_COOKIE="your_xhs_cookie"   # optional, skip if not using Xiaohongshu

# Preview mode: save to preview.html, no email sent
python3 main.py --dry-run

# Backfill a specific date's batch (Xiaohongshu searches by today's date)
python3 main.py --dry-run --date 2026-04-03

# Production run (sends email)
python3 main.py
```

---

## 📁 Project Structure

```
├── config.yml                   # ⭐ Main config (edit here)
├── main.py                      # Entry point
├── fetchers/
│   ├── arxiv_fetcher.py         # arXiv search + dedup
│   ├── arxiv_schedule.py        # arXiv announcement batch timing
│   ├── xhs_fetcher.py           # Xiaohongshu note search
│   ├── xhs_util.py              # Xiaohongshu request signing (JS crypto)
│   ├── xhs_pc_apis.py          # Xiaohongshu PC API
│   └── xhs_cookie_util.py      # Cookie string parser
├── llm/
│   ├── filter_and_summarize.py   # arXiv LLM filtering + Chinese summary
│   └── filter_and_summarize_xhs.py  # Xiaohongshu LLM filtering
├── render/
│   └── email_renderer.py        # Jinja2 HTML email renderer
├── templates/
│   └── email.html               # Email template (side-by-side layout)
├── sender/
│   └── smtp_sender.py           # SMTP sender
├── package.json                 # Node.js dependencies (Xiaohongshu signing)
├── package-lock.json            # Node.js dependency lock
├── static/
│   ├── xhs_xs_xsc_56.js         # Xiaohongshu signing JS (webpack bundle)
│   └── xhs_xray.js              # Xiaohongshu xray signing JS
└── .github/workflows/
    └── daily.yml                # GitHub Actions cron job
```

---

## 📕 Changelog

> 💡 Latest changes on top — scroll down to see how the project evolved.

### 🏷️ v1.2.1 — 2026-04-07 · Xiaohongshu LLM Parsing Fix

- 🐛 **Fix XHS column showing "LLM parse failed"**: LLM-returned note IDs didn't match candidate pool IDs, causing all score mappings to fail; added title-based fallback matching
- 🔧 **Enhanced JSON parsing**: added `_extract_json_objects()` secondary parser to extract individual JSON objects from non-standard LLM responses
- 📝 **Better fallback summaries**: when LLM completely fails, use the note's original title as summary instead of showing a technical error message
- 🪵 **Debug logging**: XHS LLM filtering now prints key status throughout (API call result, parse count, ID match details) for easier troubleshooting
- 🚫 **Remove Tab navigation**: removed click-to-switch Tab interaction, which caused display conflicts in some email clients

### 🏷️ v1.2.0 — 2026-04-07 · Xiaohongshu Experience Upgrade

- 📐 **Email layout overhaul**: replaced Tab switching with **side-by-side two-column** layout (arXiv left · XHS right), compatible with all desktop email clients
- 🧹 **LLM topic dedup**: when multiple notes cover the same topic, only the highest-scored one is kept — no more duplicate floods
- 🔄 **Smart backfill**: if dedup leaves fewer than top_n, remaining slots are auto-filled from the candidate pool by score
- ⬆️ **Node.js upgrade**: GitHub Actions Node.js 18 → 22, fixing deprecation warnings

### 🏷️ v1.1.0 — 2026-04-05 · Xiaohongshu Integration

- 📕 **Xiaohongshu search**: daily keyword-based note search with LLM filtering + Chinese summaries
- 🗓️ **Independent schedule**: XHS pushes every day — not affected by arXiv holidays (Fri/Sat/US holidays)
- 🔐 **Cookie auth**: configured via `XHS_COOKIE` secret, expires ~30 days, manual renewal needed
- 🧩 **JS signing**: Node.js executes Xiaohongshu's webpack bundle for `x-s` / `x-t` signature computation

### 🏷️ v1.0.0 — 2026-04-01 · Project Launch 🎉

- 🔍 **arXiv paper filtering**: keyword + category search, LLM smart scoring, selects Top N
- 🈶 **Dual-layer Chinese summary**: one-line summary + 100-150 char detailed breakdown
- 📬 **HTML email**: card layout + direct PDF links
- 🔄 **Deduplication**: tracks sent IDs, never sends the same paper twice
- ⚙️ **GitHub Actions deployment**: zero-server, auto-runs daily at 12:00
- 🧩 **Multi-LLM support**: MiniMax / Claude / OpenAI / DeepSeek / Zhipu / Kimi / Qwen, switch with one line

---

## 📄 License

MIT © [yzbcs](https://github.com/yzbcs)
