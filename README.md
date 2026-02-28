# GitHub Stars Organizer

把 GitHub Star 仓库按语义分类，并同步到 GitHub Lists 的半自动工作流。

## 功能概览

- 拉取并缓存你的 Star 仓库与 README 摘要
- 快照现有 GitHub Lists，兼容历史分类
- 生成分片 CSV，交给多个 agent 并行语义分类
- 合并分片结果为可审阅总表
- 人工确认后批量写回 GitHub Lists
- 可选将分类名重命名为 gitmoji 风格

## 分类集合（固定）

- `LLM/智能体`
- `前端/Web`
- `后端/API`
- `Rust/系统`
- `移动端`
- `云原生/运维`
- `数据库/存储`
- `逆向/安全`
- `编译器/语言工具链`
- `学习资源`
- `通用工具/其他`
- `代理工具`

## 环境要求

- Python 3.10+
- 可用的 GitHub PAT（通过 `GITHUB_TOKEN` 或 `GH_TOKEN` 传入）

## 目录结构

```text
scripts/
  fetch_stars_and_readmes.py        # 拉取 starred + README 缓存
  snapshot_existing_lists.py        # 快照当前 GitHub Lists
  prepare_agent_chunks.py           # 生成分片输入
  merge_agent_outputs.py            # 合并 agent 分类结果
  apply_classification_to_github.py # 将确认后的分类写回 GitHub
  rename_lists_gitmoji.py           # 可选：分类名改成 gitmoji 风格

references/
  category_rules.md                 # 分类口径与硬性规则
  subagent_prompt_template.md       # 分片分类提示词模板

.codex-output/                      # 运行产物目录（自动生成）
```

## 快速开始

1. 拉取 Star 和 README 缓存

```bash
GITHUB_TOKEN='<your_token>' python3 scripts/fetch_stars_and_readmes.py
```

2. 快照现有 Lists（用于分类兼容）

```bash
GITHUB_TOKEN='<your_token>' python3 scripts/snapshot_existing_lists.py
```

3. 生成分片输入（最多 6 片）

```bash
python3 scripts/prepare_agent_chunks.py
```

4. 分发给并行 agent 分类

- 输入：`.codex-output/agent-classify/chunk_*.csv`
- 每片输出：`.codex-output/agent-classify/out_chunk_i.csv`
- 输出列必须是：`idx,full_name,category,reason`

5. 合并所有分片结果

```bash
python3 scripts/merge_agent_outputs.py
```

6. 人工审阅总表（必须）

- 审阅文件：`.codex-output/starred_categorized_agents_final.csv`
- 建议重点检查：空分类、分类漂移、`reason` 是否合理

7. 确认后写回 GitHub Lists

```bash
GITHUB_TOKEN='<your_token>' python3 scripts/apply_classification_to_github.py
```

8. （可选）统一重命名为 gitmoji 风格

```bash
GITHUB_TOKEN='<your_token>' python3 scripts/rename_lists_gitmoji.py
```

## 关键运行产物

- `.codex-output/starred_raw.ndjson`：star 原始数据
- `.codex-output/readme_cache.json`：README 缓存
- `.codex-output/list-snapshot/membership.csv`：已有 Lists 归属
- `.codex-output/agent-classify/input_master.csv`：分类主输入
- `.codex-output/starred_categorized_agents_final.csv`：最终审阅 CSV
- `.codex-output/github-apply/apply_summary.json`：写回摘要
- `.codex-output/github-apply/apply_errors.log`：写回失败明细

## 约束与注意事项

- 分类阶段必须基于语义判断，不使用脚本打分模型直接定类。
- `apply_classification_to_github.py` 仅接受固定分类集合；存在非法分类会直接中止。
- 执行写回前务必完成人工审阅，避免错误批量同步。

## 常见问题

### 1. 报错“缺少 GITHUB_TOKEN/GH_TOKEN”

运行skills主动提供Github Token(PAT)

### 2. 合并时报 missing/dup/extra

说明分片输出不完整或重复，检查 `out_chunk_*.csv` 是否与 `chunk_*.csv` 一一对应。

### 3. 写回失败较多

查看 `.codex-output/github-apply/apply_errors.log`，通常是目标 list 缺失、仓库 node_id 缺失或 API 限流导致。

