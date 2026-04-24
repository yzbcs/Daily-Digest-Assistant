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

### Using a provider not in the list?

**No code changes needed.** Just add it in `config.yml`'s `custom_llm` block:

```yaml
llm_provider: my_api
custom_llm:
  my_api:
    sdk: openai
    base_url: "https://my-api.com/v1"
    model: "gpt-4o"
```

- `sdk`: `"openai"` (OpenAI-compatible) or `"anthropic"` (Anthropic-compatible)
- `base_url`: your API endpoint
- `model`: model name

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

# Custom LLM provider (for non-built-in services)
custom_llm: {}
# custom_llm:
#   my_api:
#     sdk: openai
#     base_url: "https://my-api.com/v1"
#     model: "gpt-4o"

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
│   ├── email.html               # Email template (side-by-side layout)
│   └── study_index.html         # GitHub Pages archive page template
├── scripts/
│   └── update_study_data.py    # Updates GitHub Pages archive index data.json
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

## 🌐 Push to GitHub Pages (Optional)

Your daily digest HTML can also be archived on your GitHub Pages site (`yzbcs.github.io/study/`).

### Prerequisites

1. You have a `yzbcs/yzbcs.github.io` repository (deployed as GitHub Pages)
2. Generate a **Personal Access Token** (classic, with `repo` scope)
3. Add a Secret in this repo:
   - Go to **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `Yzbcs_TOKEN`
   - Secret: paste your PAT

### Target Repo Init

In `yzbcs/yzbcs.github.io` on the `main` branch, add:

**`study/data.json`**:
```json
{"notes": []}
```

### How It Works

After each daily push, the workflow automatically:
1. Copies `preview.html` to `study/daily/YYYY/MM/YYYY-MM-DD.html`
2. Updates `study/data.json` index
3. Pushes to `yzbcs/yzbcs.github.io`

Live at: `https://yzbcs.github.io/study/`

> ⚠️ Fork users will NOT trigger this — only the original repo owner.

---

## 📄 License

MIT © [yzbcs](https://github.com/yzbcs)
