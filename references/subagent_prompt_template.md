请仅处理分片文件：`<chunk_path>`。

你不是唯一在仓库工作的 agent；忽略其他改动，不要编辑职责外文件。

任务要求：

1. 逐行读取 `description + topics + readme_excerpt + existing_lists`
2. 基于“主用途”做语义分类，不使用脚本打分
3. 若命中 `skills/agent/mcp/prompt/rag` 且主用途为 AI，归 `LLM/智能体`
4. 若命中 `xray/v2ray/mihomo/sing-box/clash` 主用途，归 `代理工具`
5. 尽量结合 `existing_lists` 做兼容判断（不是强制）

可选分类集合（仅能使用这些）：

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

输出文件：`<out_chunk_path>`

输出列：`idx,full_name,category,reason`

- `idx/full_name` 必须与输入一致
- `reason` 必须中文，建议 8-20 字，说明主要依据
