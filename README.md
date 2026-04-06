# 📄 Arxiv Daily Digest

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" />
  <img src="https://img.shields.io/badge/License-MIT-green" />
  <img src="https://img.shields.io/badge/LLM-MiniMax%20%7C%20Claude%20%7C%20OpenAI-orange" />
  <img src="https://img.shields.io/badge/Deploy-GitHub%20Actions-black?logo=github" />
</p>

<p align="center">
  <b>每个工作日中午 12 点，把最新 arXiv 论文精选自动推进你的邮箱。</b><br/>
  LLM 智能筛选 + 中文摘要 + 详细解读，fork 即用，无需服务器。
</p>

---

## 📸 效果预览

邮件以卡片形式展示每篇论文，包含一句话总结和可展开的详细解读：

- **一句话总结**：快速判断是否值得细读
- **详细解读**：点击展开，查看论文做了什么、核心创新点、主要结论
- **直达链接**：arXiv 原文 + PDF 一键跳转

---

## ✨ 核心功能

- 🔍 **精准时间对齐**：按 arXiv 官方公告批次抓取，不漏批、不重复
- 🤖 **LLM 智能筛选**：自动从候选中精选最相关的 Top 10，低相关论文过滤不推
- 🈶 **中文双层摘要**：一句话总结 + 100-150 字详细解读，阅读效率翻倍
- 📬 **HTML 邮件推送**：精美卡片排版，支持展开/收起详情
- 🔄 **去重机制**：记录已推送论文，不重复推送
- 🧩 **多 LLM 支持**：Claude / MiniMax / OpenAI / DeepSeek / 智谱 / Kimi / 通义，一行配置切换
- ⚙️ **零服务器部署**：完全基于 GitHub Actions，免费自动运行

---

## 🚀 快速开始（5 分钟）

### 第一步：Fork 本仓库

点击右上角 **Fork**，将仓库复制到你的 GitHub 账号下。

### 第二步：改关键词

编辑 `config.yml`，填写你关心的关键词和分类（其他选项可以先不动）：

```yaml
keywords:
  - agent          # 关键词支持多个，只要论文命中任意一个就会进入候选
  - skill
  - your_keyword

categories:        # arxiv 分类，留空则搜全类别
  - cs.AI
  - cs.LG
```

### 第三步：配置 GitHub Secrets

进入你 fork 的仓库 → **Settings → Secrets and variables → Actions → New repository secret**，添加以下 4 个密钥：

| Secret 名称 | 说明 |
|------------|------|
| `LLM_API_KEY` | LLM 服务的 API Key |
| `EMAIL_USER` | 发件邮箱地址（163 / Gmail / QQ）|
| `EMAIL_PASS` | 发件邮箱**授权码**（非登录密码，见下方说明）|
| `EMAIL_TO` | 收件邮箱地址 |

### 第四步：手动触发一次验证

进入 **Actions → Daily Paper Digest → Run workflow**，手动触发一次，确认邮件正常收到。

之后每个工作日（周一至周五）北京时间 **12:00** 自动推送。

---

## 📮 邮箱授权码获取

> 授权码 ≠ 登录密码，是专门用于第三方客户端的单独密码。

- **163 邮箱**：网页版 → 设置 → POP3/SMTP/IMAP → 开启 SMTP → 生成授权码
- **Gmail**：开启两步验证 → 安全 → 应用专用密码 → 生成
- **QQ 邮箱**：设置 → 账户 → 开启 SMTP → 获取授权码

---

## 🔧 支持的 LLM 提供商

在 `config.yml` 中修改 `llm_provider` 即可切换，填写下表中的 provider 名称：

| provider | 服务商 | 推荐理由 |
|----------|--------|---------|
| `minimax` | MiniMax M2.7 | 默认推荐，推理能力强，筛选质量高 |
| `claude` | Anthropic Claude Haiku | 速度快，输出稳定 |
| `openai` | OpenAI GPT-4o mini | 通用性好 |
| `deepseek` | DeepSeek | 国内访问快，性价比高 |
| `zhipu` | 智谱 GLM | 国内备选 |
| `moonshot` | 月之暗面 Kimi | 国内备选 |
| `qwen` | 阿里通义千问 | 国内备选 |

> 新增提供商只需在 `llm/filter_and_summarize.py` 的 `PROVIDER_REGISTRY` 里加一行。

---

## ⚙️ 完整配置说明

`config.yml` 中所有可配置项：

```yaml
# 论文关键词（OR 关系，命中任意一个即进入候选）
keywords:
  - agent
  - skill
  - openclaw

# arxiv 分类过滤（留空则搜索全部分类）
# 常用分类：cs.AI cs.LG cs.RO cs.CL cs.CV
categories:
  - cs.AI
  - cs.LG
  - cs.RO

# 每日最多推送篇数
max_papers: 10

# LLM 评分门槛（1-10），低于此分的论文不推送
# 调高（如 8）→ 更严格，推送更少但更相关
# 调低（如 4）→ 更宽松，推送更多
min_score: 6

# 候选池大小：先从 arxiv 搜索这么多篇，再让 LLM 筛选
candidate_pool: 50

# 发件邮箱服务商
smtp_provider: "163"   # 可选：163 / gmail / qq

# LLM 服务商
llm_provider: minimax  # 可选：minimax / claude / openai / deepseek / zhipu / moonshot / qwen
```

---

## 💻 本地运行 / 测试

```bash
git clone https://github.com/yzbcs/Arxiv-Daily-Digest.git
cd Arxiv-Daily-Digest
pip install -r requirements.txt

export LLM_API_KEY="your_api_key"
export EMAIL_USER="xxx@163.com"
export EMAIL_PASS="your_smtp_password"
export EMAIL_TO="xxx@qq.com"

# 预览模式：不发邮件，结果保存到 preview.html
python3 main.py --dry-run

# 补跑指定日期的论文批次
python3 main.py --dry-run --date 2026-04-03

# 正式运行（发送邮件）
python3 main.py
```

---

## 📁 项目结构

```
├── config.yml                   # ⭐ 用户配置（改这里就够了）
├── main.py                      # 主入口，串联各模块
├── fetchers/
│   ├── arxiv_fetcher.py         # arXiv 搜索 + 去重
│   └── arxiv_schedule.py        # arXiv 公告批次时间计算
├── llm/
│   └── filter_and_summarize.py  # LLM 筛选 + 中文摘要
├── render/
│   └── email_renderer.py        # Jinja2 渲染 HTML 邮件
├── templates/
│   └── email.html               # 邮件模板
├── sender/
│   └── smtp_sender.py           # SMTP 发送
├── data/
│   └── sent_ids.json            # 已推送记录（自动维护）
└── .github/workflows/
    └── daily.yml                # GitHub Actions 定时任务
```

---

## 📄 License

MIT © [yzbcs](https://github.com/yzbcs)
