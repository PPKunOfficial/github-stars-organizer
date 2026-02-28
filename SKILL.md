---
name: github-stars-organizer
description: "Organize GitHub starred repositories with a human-in-the-loop workflow: request PAT first, fetch and cache starred repos with README content, dispatch subagents for chunked semantic classification, merge into review CSV, propose gitmoji-style category names, apply user edits, and sync approved results to GitHub Lists."
---

# GitHub Stars Organizer

## Core Workflow

1. 索要 PAT（第一步必须执行）
2. 拉取并缓存 `star + README`
3. 拉取现有 GitHub Lists 快照
4. 生成分片输入，召唤 subagent 分段语义分类
5. 主 agent 合并分片 CSV，输出建议分类与 gitmoji 名称
6. 询问用户是否调整分类或新增分类条目
7. 生成最终 CSV 供用户核对
8. 用户确认后再脚本提交到 GitHub

## Mandatory Rules

- 技能加载后第一时间索要 PAT。
- 用户未确认前，不执行线上写入。
- 分类阶段禁止脚本打分（不使用关键词权重模型给出最终类别）。
- 分类阶段必须由 subagent 分段阅读 `description + topics + readme_excerpt` 做语义判断。
- 默认分类名称使用 gitmoji 样式。
- 结合用户已有 Lists 给出“沿用/新增”建议，不要无视历史分类体系。

## Commands

在仓库根目录执行：

1. 抓取并缓存数据：

```bash
GITHUB_TOKEN='<token>' python3 .codex-output/skills/github-stars-organizer/scripts/fetch_stars_and_readmes.py
```

2. 快照现有 Lists（用于结合旧分类）：

```bash
GITHUB_TOKEN='<token>' python3 .codex-output/skills/github-stars-organizer/scripts/snapshot_existing_lists.py
```

3. 生成分片输入：

```bash
python3 .codex-output/skills/github-stars-organizer/scripts/prepare_agent_chunks.py
```

4. 分片分类完成后合并：

```bash
python3 .codex-output/skills/github-stars-organizer/scripts/merge_agent_outputs.py
```

5. 用户确认后提交到 GitHub Lists：

```bash
GITHUB_TOKEN='<token>' python3 .codex-output/skills/github-stars-organizer/scripts/apply_classification_to_github.py
```

6. 按需重命名 Lists 为 gitmoji 风格：

```bash
GITHUB_TOKEN='<token>' python3 .codex-output/skills/github-stars-organizer/scripts/rename_lists_gitmoji.py
```

## Subagent Dispatch

- 分片输入：`.codex-output/agent-classify/chunk_*.csv`
- 每个 subagent 只负责一个分片，输出 `.codex-output/agent-classify/out_chunk_i.csv`
- 输出列固定：`idx,full_name,category,reason`
- `reason` 必须是中文短句，说明主用途依据

使用 [subagent_prompt_template.md](references/subagent_prompt_template.md) 作为模板。

## Review & Suggestion Phase

主 agent 在合并后必须先输出：

1. 现有分类分布
2. 与旧 Lists 的重叠情况
3. 建议的最终分类集（默认 gitmoji 命名）
4. 建议新增/合并/拆分项

然后询问用户是否要修改分类条目或名称。  
只有用户明确确认后，才执行提交脚本。

## Resources

### scripts/

- `fetch_stars_and_readmes.py`: 使用 PAT 抓取 star 与 README 缓存
- `snapshot_existing_lists.py`: 导出现有 Lists 与仓库归属
- `prepare_agent_chunks.py`: 生成分片输入 CSV
- `merge_agent_outputs.py`: 合并分片结果为最终候选 CSV
- `apply_classification_to_github.py`: 提交最终分类到 GitHub Lists
- `rename_lists_gitmoji.py`: 批量改名为 gitmoji 风格

### references/

- `category_rules.md`: 分类口径与硬性覆盖规则
- `subagent_prompt_template.md`: subagent 分类指令模板
