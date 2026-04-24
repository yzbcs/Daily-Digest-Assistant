# 🚀 本周必做 Quick Wins

> 每项耗时 **< 30 分钟**，完成后仓库专业感瞬间提升，fork 用户转化率显著提高。

---

## 📊 总览

| 指标 | 数值 |
|------|------|
| 总任务数 | **6 项** |
| 预计总耗时 | **约 65 分钟** |
| 涉及文件 | `LICENSE`, `README.md`, `.gitignore` |
| 零代码改动 | 第 1~5 项完全零风险 |

---

## 任务清单

### 1. 添加 LICENSE 文件（⏱️ 5 分钟）

**说明**
当前仓库无开源协议，用户不敢 Fork 用于生产环境。MIT 协议最宽松，适合本项目。

**操作步骤**
1. 在仓库根目录创建 `LICENSE` 文件
2. 内容使用 [MIT 协议模板](https://choosealicense.com/licenses/mit/)：

```
MIT License

Copyright (c) 2026 [你的名字或用户名]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

**预期效果**
- 仓库主页右侧出现 "MIT" 协议标识
- 用户可以放心 Fork 和商用

---

### 2. README 顶部添加 Badge 徽章行（⏱️ 10 分钟）

**说明**
在 README 最顶部添加一行 shields 徽章，一眼展示项目活跃度和可靠性。

**操作步骤**
编辑 `README.md`，在标题 `# 📬 每日推送助手` 下方添加：

```markdown
<p align="center">
  <a href="https://github.com/yzbcs/Daily-Digest-Assistant/stargazers"><img src="https://img.shields.io/github/stars/yzbcs/Daily-Digest-Assistant?style=flat-square&logo=github&color=yellow" alt="Stars" /></a>
  <a href="https://github.com/yzbcs/Daily-Digest-Assistant/network/members"><img src="https://img.shields.io/github/forks/yzbcs/Daily-Digest-Assistant?style=flat-square&logo=github&color=blue" alt="Forks" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python" alt="Python" /></a>
  <a href="https://github.com/yzbcs/Daily-Digest-Assistant/actions"><img src="https://img.shields.io/github/actions/workflow/status/yzbcs/Daily-Digest-Assistant/daily.yml?style=flat-square&logo=github-actions&label=Actions" alt="Actions" /></a>
</p>
```

> 注意：需将 `yzbcs/Daily-Digest-Assistant` 替换为你的实际仓库路径。

**预期效果**
- 仓库主页瞬间有"高 star 项目"的观感
- 用户一眼看出项目活跃、持续维护

---

### 3. README 添加实际效果截图（⏱️ 15 分钟）

**说明**
放一张真实邮件效果截图（脱敏处理），让 fork 用户提前知道"推送长什么样"。

**操作步骤**
1. 运行一次 `python3 main.py --dry-run` 生成本地 `preview.html`
2. 用浏览器打开 `preview.html`，截图邮件效果（建议 1200px 宽度）
3. 截图中敏感信息（邮箱地址、具体论文内容）做模糊处理
4. 保存为 `assets/screenshot.png`（或 `_image/screenshot.png`）
5. 在 README "效果预览" 章节插入：

```markdown
## 📸 效果预览

邮件采用 **并排双栏布局**，左栏 arXiv 论文、右栏小红书笔记：

<img src="_image/screenshot.png" width="800" alt="邮件效果预览">

- **arXiv 论文**：一句话总结 + 详细解读 + PDF 链接；休息日显示"今天我们休息～"
- **小红书笔记**：内容总结 + 跳转链接；每天更新（不受 arXiv 休息日影响）
```

**预期效果**
- 用户 fork 前就知道"我每天会收到什么样的邮件"
- 大幅降低决策成本，提高转化率

---

### 4. 清理已提交的 `__pycache__`（⏱️ 10 分钟）

**说明**
当前 `fetchers/__pycache__/`、`llm/__pycache__/` 已污染仓库，需彻底清理并在 `.gitignore` 中加强规则。

**操作步骤**

```bash
# 1. 删除已跟踪的 pycache 目录
git rm -r --cached fetchers/__pycache__
git rm -r --cached llm/__pycache__
git rm -r --cached render/__pycache__
git rm -r --cached sender/__pycache__

# 2. 确保 .gitignore 包含以下规则
cat >> .gitignore << 'EOF'

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Environment
.env
.venv
env/
venv/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db
EOF

# 3. 提交
git add .gitignore
git commit -m "chore: remove pycache and strengthen .gitignore"
```

**预期效果**
- 仓库体积减小
- 后续 PR 不再出现 pycache 噪音
- 符合 Python 项目规范

---

### 5. README 顶部放"Fork 按钮"直达链接（⏱️ 5 分钟）

**说明**
在 README 最显眼的位置放一个直达 fork 页面的链接，减少用户操作步骤。

**操作步骤**
编辑 `README.md`，在标题和 Badge 下方添加：

```markdown
<p align="center">
  <a href="https://github.com/yzbcs/Daily-Digest-Assistant/fork">
    <img src="https://img.shields.io/badge/Fork-本仓库-181717?style=for-the-badge&logo=github&logoColor=white" alt="Fork">
  </a>
</p>
```

或者更简洁的纯文本引导：

```markdown
> 🚀 **30 秒部署**：点击右上角 [Fork 本仓库](https://github.com/yzbcs/Daily-Digest-Assistant/fork) → 添加 Secrets → 坐等每日推送
```

**预期效果**
- 用户从"看到这个项目"到"完成 Fork"只需一次点击
- 转化率提升

---

### 6. 制作"30 秒部署演示"GIF（⏱️ 20 分钟）

**说明**
录一段从 fork → 添加 secret → 收到第一封邮件的完整流程，放在 README 最顶部。这是高 star 项目的标配。

**操作步骤**
1. 使用 [ScreenToGif](https://www.screentogif.com/)（Windows）或 [Kap](https://getkap.co/)（Mac）录制
2. 录制内容（控制在 30 秒内）：
   - 点击 "Fork" 按钮
   - 进入 Settings → Secrets → New repository secret
   - 依次添加 `LLM_API_KEY`、`EMAIL_USER`、`EMAIL_PASS`、`EMAIL_TO`
   - 进入 Actions → Daily Paper Digest → Run workflow
   - 切换到邮箱收件箱，展示收到的邮件
3. 导出为 GIF（建议宽度 800px，文件大小 < 2MB）
4. 保存到 `_image/deploy-demo.gif`
5. 在 README 最顶部插入：

```markdown
<p align="center">
  <img src="_image/deploy-demo.gif" width="800" alt="30秒部署演示">
</p>
```

> 如果不想录真实操作，可以用 [asciinema](https://asciinema.org/) 录制终端操作，或用静态截图拼图替代。

**预期效果**
- 用户看到"原来这么简单"，立即动手 fork
- 大幅降低首次使用的心理门槛
- 这是从 "1k stars" 到 "10k stars" 的关键差异项

---

## ✅ 完成检查清单

完成每一项后在此打勾：

- [ ] 1. LICENSE 文件已添加
- [ ] 2. README Badge 行已添加
- [ ] 3. 效果截图已添加并脱敏
- [ ] 4. `__pycache__` 已清理，`.gitignore` 已加强
- [ ] 5. Fork 直达链接已添加
- [ ] 6. 部署演示 GIF/截图已添加

---

> ⏰ **总耗时预估**：约 65 分钟（纯文本操作约 45 分钟，截图/GIF 约 20 分钟）
> 
> 完成后建议更新 `docs/todo.md` 中对应项的状态为 ✅，并推进到 P1 阶段。
