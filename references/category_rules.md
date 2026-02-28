# Category Rules

## Categories

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

## Default Gitmoji Names

- `🤖 llm-agent`
- `💄 web-ui`
- `🛠️ backend-api`
- `🦀 rust-system`
- `📱 mobile`
- `☁️ cloud-devops`
- `🗃️ db-storage`
- `🔐 reverse-sec`
- `🧪 compiler-toolchain`
- `📚 learning-resources`
- `🧰 misc-tools`
- `🧭 proxy-tools`

## Priority

1. `学习资源`
2. `LLM/智能体`
3. `代理工具`
4. 其余类别

## Hard Overrides

- 命中 `skills/skill/agent/mcp/prompt/rag` 且 README 主用途为 AI 工作流时：归 `LLM/智能体`
- 命中 `xray/v2ray/mihomo/sing-box/clash/shadowsocks/trojan/hysteria/shadowrocket/surge`：归 `代理工具`
- 命中 `hexrays` 不等于命中 `xray`，避免误判

## Output Requirements

- 始终输出可审阅 CSV
- CSV 必须包含：`full_name`, `category`, `reason`
- `reason` 使用一句中文说明主要依据
- 合并阶段额外输出：`existing_lists`，用于和历史分类对齐
