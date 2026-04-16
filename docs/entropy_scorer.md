# 熵机制筛选模块（SLTF-Entropy）

## 1. 设计动机

原有的 LLM 筛选方式依赖大模型语义理解，效果好但存在两个问题：
- **API 调用成本高**：每次需要将所有候选论文（可达 50+ 篇）全部发送给 LLM
- **速度慢**：LLM 生成摘要需要等待，且受限于 API 限速

因此引入 SLTF-Entropy 作为轻量级预筛层，在不调用 LLM 的情况下快速从大批量论文中筛选最相关的 top_n 篇，再由 LLM 生成摘要。

## 2. 核心原理

### 2.1 两阶段筛选流程

```
候选论文 → 初筛（关键词命中）→ SLTF-Entropy 评分排序 → top_n → LLM 生成摘要
```

### 2.2 初筛阶段

过滤掉完全不相关论文，必须满足：
- 标题或摘要中**至少包含一个关键词**（大小写不敏感）

### 2.3 SLTF-Entropy 评分

参考原论文公式：

```
Score(d,q) = (1/E_d) × Σ_{t∈q∩d} log(1 + TF_title(t,d)×2 + TF_abstract(t,d)×1)
```

**各部分含义**：

| 符号 | 含义 |
|------|------|
| `E_d` | 文档 d 中所有 term 的 Shannon 熵，越高说明 term 分布越均匀、区分度越强 |
| `TF_title(t,d)` | 关键词 t 在标题中出现的次数 |
| `TF_abstract(t,d)` | 关键词 t 在摘要中出现的次数 |
| `log(1+TF)` | 压缩高频 term，防止一个词出现多次就压制其他词 |

**Shannon 熵计算**：

```
E_d = -Σ p_i log2(p_i)
其中 p_i = TF(t_i) / Σ TF(t_j)
```

### 2.4 关键词权重

- 多词短语（空格分隔）：权重 × 1.5
- 单词关键词：权重 × 1.0

### 2.5 评分特点

| 特性 | 说明 |
|------|------|
| 标题双倍权重 | 标题命中比摘要命中更有参考价值 |
| 熵归一化 | 对文档长度鲁棒，关键词均匀分布的论文得分更高 |
| log 压缩 | 避免高频 term 压制其他词 |
| 额外 arxiv 热度加分 | `score += paper.get("score", 0) × 0.1` |

### 2.6 LLM 摘要生成

熵筛选后，top_n 篇论文交给 LLM 生成摘要（`summary_zh` + `detail_zh`）。此时 LLM 只负责生成，不做相关性评分，因为熵分已决定排序。

Prompt 模板告知 LLM：
- 关注方向（config.yml 中的 keywords）
- 摘要格式要求（一句总结 20-40 字，详细解读 100-150 字）
- 按熵分高低作为参考

## 3. 代码结构

```
llm/
├── filter_and_summarize.py   # 原有 LLM 筛选（语义评分 + 摘要生成）
└── entropy_scorer.py         # 熵筛选模块
    ├── _tokenize()           # 小写化 + 分词
    ├── _build_tf()           # 统计 term 频次
    ├── _compute_shannon_entropy()  # 计算 Shannon 熵
    ├── _score_single_paper()  # 单篇论文 SLTF-Entropy 评分
    ├── score_papers_by_sltf_entropy()  # 批量评分排序
    ├── _build_keyword_tiers() # 关键词优先级衍生
    ├── _build_entropy_paper_prompt()  # LLM prompt 构造
    ├── _generate_summaries_with_llm()  # LLM 生成摘要
    └── entropy_filter_papers()  # 入口函数
```

## 4. 使用方式

```bash
# 熵筛选模式（熵筛选 + LLM 生成摘要）
python3 main.py --entropy-only

# 熵筛选 + 预览模式（不发送邮件）
python3 main.py --entropy-only --dry-run

# 原有 LLM 筛选模式
python3 main.py

# 原有 LLM 筛选 + 预览模式
python3 main.py --dry-run
```

## 5. 与 LLM 筛选模式的对比

| 特性 | 熵筛选模式 | LLM 筛选模式 |
|------|-----------|-------------|
| 筛选依据 | SLTF-Entropy 关键词命中 | LLM 语义理解 |
| 排序方式 | 确定性（相同输入=相同结果） | 可能波动 |
| API 调用 | 是（仅生成摘要） | 是（评分 + 摘要） |
| 速度 | 快（熵筛选 < 1s） | 慢（需等 LLM 评分） |
| 适用场景 | 精准关键词匹配、API 成本敏感 | 语义复杂、需深度理解 |

## 6. 示例演算

**关键词**：`['deep learning', 'entropy', 'LRM']`

**论文 A**：`"Deep Learning for Computer Vision"`
- TF(deep)=1, TF(learning)=1, TF(title)=2 → log(1+2×1)=1.099
- TF(entropy)=0 → 不贡献
- TF(LRM)=0 → 不贡献
- TF 总数=10，熵=3.322
- Score = (1/3.322) × 1.099 × 1.5 = **0.496**

**论文 B**：`"Entropy Mechanism in Large Reasoning Models"`
- TF(entropy)=1 → log(1+1×1)=0.693
- TF(LRM)=1 → log(1+1×1)=0.693
- Score = (1/E) × (0.693×1.0 + 0.693×1.5) = **0.611** > 论文 A

## 7. 注意事项

- 熵筛选依赖**关键词精确匹配**，无法理解同义词
- 对于语义复杂的研究方向，建议仍用 LLM 筛选模式
- `--entropy-only` 适合关键词明确的垂直领域
