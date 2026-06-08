# cc-mirror

## 1. 项目基本信息

- **项目名**：CC-MIRROR（numman-ali/cc-mirror）
- **GitHub**：https://github.com/numman-ali/cc-mirror
- **Star 数 / 主要语言**：2.2k / TypeScript
- **简介**（≤200 字）：

把 Claude Code 克隆成多个隔离的"variant"，每个 variant 可以指向不同的 LLM provider（Z.ai、MiniMax、Kimi、OpenRouter、Ollama、Vercel AI Gateway 等），并应用各自的 prompt pack 和 tweakcc 主题。每个 variant 是完全独立的 Claude Code 安装实例：自己的 config、session、MCP server、credentials、可执行文件名（如 `mclaude`、`zai`、`kimi`），互不干扰。本质：把"切换 LLM provider"这件事工程化为"创建一个独立 Claude Code 副本"。

- **核心创新（一句话）**：通过克隆 Claude Code 到隔离目录并改写 provider endpoint 实现多 LLM 后端"统一适配"，每个 variant 是独立可执行命令，不需要写真正的协议适配代码。

## 2. 项目架构概览

### 技术栈

- **语言**：TypeScript（Node.js CLI）
- **分发方式**：npm 包（`cc-mirror`），通过 `npx cc-mirror` 调用
- **核心依赖**：底层是 Anthropic 官方 Claude Code（克隆并修改环境变量）
- **可选依赖**：tweakcc（主题定制）、provider 各自的 SDK（如 OpenRouter、Vercel AI Gateway）
- **License**：MIT

### 目录结构

```
cc-mirror/
├── src/                            ← 核心 TS 源码
│   ├── core/                       ← 核心：variant 创建、管理、状态持久化
│   ├── providers/                  ← 各 LLM provider 的配置预设
│   ├── brands/                     ← 各 provider 的主题/品牌包
│   ├── cli/                        ← CLI 入口与子命令
│   └── tui/                        ← 交互式 wizard TUI
├── scripts/                        ← 构建/发布脚本
├── docs/                           ← 文档
│   ├── architecture/               ← 架构说明
│   └── features/                   ← 各 provider 特性说明
├── test/                           ← 测试
├── assets/                         ← 截图
├── DESIGN.md          (5 KB)       ← 设计文档
├── AGENTS.md         (12 KB)       ← Agent 配置说明
├── eslint.config.js
├── lefthook.yml                    ← Git hooks（commit / pre-push 检查）
├── package.json
└── tsconfig.json
```

### 用户视角的"运行时目录"

每个 variant 在用户家目录下有独立目录：

```
~/.cc-mirror/
├── mclaude/                        ← Mirror Claude variant
│   ├── native/                     ← 该 variant 的 Claude Code 安装
│   ├── config/                     ← 该 variant 的 config（API keys / sessions / MCP）
│   ├── tweakcc/                    ← 该 variant 的主题
│   └── variant.json                ← 元数据（provider / version / 创建时间等）
├── zai/                            ← Z.ai variant（GLM 模型）
├── minimax/                        ← MiniMax variant（M2.5）
├── kimi/                           ← Kimi Code variant
└── ... 其他 variant
```

每个 variant 有 wrapper 脚本投放到 `~/.local/bin/<variant-name>`（macOS/Linux）或 `~/.cc-mirror/bin/<variant-name>.cmd`（Windows）。用户在终端直接输入 `mclaude`、`zai` 就能启动对应 variant。

### 核心机制

**一句话**：克隆 Claude Code 到独立目录、写入对应 provider 的环境变量与配置、生成可执行 wrapper——不写适配协议代码，让 Claude Code 本身去和不同 endpoint 通信。

执行 `npx cc-mirror quick --provider zai --name zai-claude` 时，cc-mirror：①克隆 Claude Code 安装到 `~/.cc-mirror/zai-claude/native/`；②写入 `variant.json` 标记 provider；③根据 provider 预设把环境变量（如 `ANTHROPIC_BASE_URL`、`ANTHROPIC_API_KEY`、模型映射 `model-sonnet`/`model-opus`/`model-haiku`）写入该 variant 的 config；④可选地应用 prompt pack（变更 system prompt 模板）和 tweakcc 主题（终端颜色/视觉）；⑤在 PATH 目录生成 wrapper 脚本，启动时进入该 variant 的隔离环境。最终用户运行 `zai-claude` 时实际跑的是 Claude Code，但所有 API 请求被 base_url 指向 Z.ai endpoint，模型名被映射成 GLM-5。这是"零协议代码"的适配——把适配工作甩给 Claude Code 自己处理（因为大多数 provider 提供 OpenAI/Anthropic 兼容接口）。

## 3. 可参考的设计点

**最值得关注的 3 个设计**：

1. **零协议代码的适配策略**：不写真正的适配器，靠"克隆原 CLI + 改环境变量 + 改 base_url + 改模型映射"实现多 LLM 接入。这种"借力打力"的思路适合所有"目标 LLM 提供 OpenAI/Anthropic 兼容接口"的场景。
2. **variant 隔离架构**：每个 variant 是独立目录 + 独立可执行命令，配置/会话/MCP server/credentials 完全隔离。多个 variant 可以同时运行不互相影响。
3. **provider 预设系统（`providers/`）**：每个 LLM provider 一个预设，包含 base_url、模型映射、prompt pack、主题。新增 provider 只需要加一个预设文件，不改主代码。

| 项目模块 | 它解决的问题 | 实现方式 |
|---|---|---|
| `src/core/` | variant 怎么创建/更新/删除 | 状态机 + 文件系统操作（克隆、写 config、生成 wrapper） |
| `src/providers/` | 怎么支持多种 LLM 后端 | 预设文件，每个 provider 一个，含 base_url/模型映射/auth 方式 |
| `src/brands/` | 不同 provider 视觉差异化 | tweakcc 主题包，每个 provider 一套配色 |
| `src/cli/` | CLI 入口 | 子命令模式（quick / create / list / update / remove / doctor / tweak / apply） |
| `src/tui/` | 交互式 wizard | TUI 引导用户选 provider、填 API key、命名 variant |
| `~/.cc-mirror/<variant>/native/` | 独立的 Claude Code 安装 | 每个 variant 一份完整的 Claude Code 副本 |
| `variant.json` | variant 元数据 | provider 类型、版本、模型映射、创建时间等 |
| `wrappers (mclaude / zai / ...)` | 一键启动对应 variant | 生成的 shell/cmd 脚本，设置环境后启动该 variant 的 Claude Code |
| `--claude-version <stable\|latest\|2.1.37>` | Claude Code 版本管理 | 安装/更新时 resolve 到具体版本号写入 variant.json |
| `update` 子命令 | 升级 variant | 重新拉取上游 + 保留本地 config + 重新应用主题 |
| `doctor` 子命令 | 健康检查 | 验证所有 variant 的安装完整性、配置有效性 |
| `apply` 子命令 | 重新应用主题 | 不重装，仅重新跑 tweakcc patches |
| `--no-tweak` / `--no-prompt-pack` | 跳过可选增强 | flag 控制，可只装最小变体 |

### 详细说明

- **零协议代码适配**：cc-mirror 不写"如何把 Anthropic 请求转成 Z.ai 请求"这种代码。它依赖一个事实：大多数现代 LLM provider 都提供 Anthropic 或 OpenAI **兼容的 HTTP 接口**。Claude Code 内部把请求发到 `ANTHROPIC_BASE_URL`，cc-mirror 把这个 URL 改成 `https://api.z.ai/...`，Z.ai 自己处理协议兼容。这是借势设计——把适配责任甩给上游 provider。

- **variant 完全隔离**：`~/.cc-mirror/<name>/` 是该 variant 的全部数据。如果某个 variant 配置坏了，删除整个目录即可，不影响其他。这种"文件系统级隔离"避免了所有"全局 config 互相覆盖"的常见坑。

- **provider 预设文件**：`src/providers/` 里每个 provider 一个文件（推测格式），声明 `base_url`、`auth_type`（API Key / OAuth / Token）、`model_mapping`（sonnet/opus/haiku → 该 provider 的实际模型名）、`prompt_pack`（针对该 provider 的 prompt 优化）、`brand`（默认主题）。新增 provider = 加一个文件 + 一个主题。

- **wrapper 脚本机制**：用户运行 `mclaude` 实际是运行 `~/.local/bin/mclaude` wrapper 脚本。脚本的工作：①设置环境变量（指向该 variant 的 config 目录、API key、base_url）；②cd 到该 variant 的 native 目录；③启动 Claude Code 二进制。Windows 版本同时生成 `.cmd` 和 `.mjs` 启动器。

- **`variant.json` 元数据**：记录 provider 类型、Claude Code 版本（pin 后的具体版本号）、模型映射、创建时间、最后更新时间、tweakcc 应用状态。这是 variant 的"身份证"，update/doctor 命令读它判断状态。

- **`update [name|all]`**：单独更新一个 variant 或所有 variant。逻辑：拉新版 Claude Code、保留本地 config 不动、重新应用 prompt pack 和 tweakcc 主题。这是"基础设施版本管理"的标准做法。

- **`doctor` 健康检查**：扫描所有 variant，检查二进制存在/wrapper 可执行/config 完整/API endpoint 可达。这是让用户能自助排错的关键命令——多 variant 系统出问题不容易定位，doctor 给出明确诊断。

- **`apply <name>`（不重装）**：用户只想换主题或更新 prompt pack，不需要重装 Claude Code。这种"细粒度更新"在维护成本上很关键。

- **`tweak <name>` 启动 tweakcc**：调用第三方工具 [tweakcc](https://github.com/Piebald-AI/tweakcc) 让用户深度定制视觉。这种"集成而非重造"的工程哲学减少了项目自身复杂度。

- **品牌主题 9 种**：每个 provider 有专属配色（Kimi 是青绿、MiniMax 是珊瑚红、Z.ai 是黑金、OpenRouter 是银铬蓝等）。视觉差异化让用户在多个终端窗口里能直观区分自己在用哪个 variant。

## 4. 关键细节

- **整个项目代码量极小**：`src/` 只有 5 个子目录（brands、cli、core、providers、tui），加起来推测不超过几千行 TS。这种"轻量+功能完整"的实现是可借鉴的工程范本。
- **`DESIGN.md` 5 KB**：项目自带的设计文档，简明描述 cc-mirror 的核心设计决策。这是开源项目里少见的、能直接读完的设计文档。
- **`AGENTS.md` 12 KB**：详细描述每个 provider 的支持情况、限制、最佳实践。这是"用户文档"和"维护文档"的混合体。
- **`lefthook.yml`**：用 lefthook 做 git hooks（commit/pre-push 自动跑 lint 和测试）。反映项目工程纪律。
- **`.c8rc.json`**：c8 是 Node.js 测试覆盖率工具的配置。说明项目有测试覆盖率要求。
- **支持 9 种 provider + custom**：Kimi、MiniMax、Z.ai、OpenRouter、Vercel、Ollama、NanoGPT、CCRouter、GatewayZ + 自定义。覆盖了主流国内外 LLM provider。
- **支持 Claude Code 版本管理（stable/latest/pin）**：用户可以选择跟踪上游稳定通道、最新通道、或锁定具体版本号。这是面向"工具链稳定性"的设计——不让上游升级破坏用户工作流。
- **Windows 兼容性专门处理**：每个 wrapper 同时生成 `.cmd`（Windows 批处理）和 `.mjs`（Node.js 启动器）。README 也专门写了 Windows 用户的 PATH 配置注意事项。这是跨平台 CLI 的工程素养体现。
- **`opinionated distribution` 自我定位**：作者明确说这是"opinionated"（带主观倾向的）发行版——做了很多默认决策（哪个模型映射到 sonnet、什么主题搭配、prompt pack 怎么写）。这种"我已经替你想好"的产品策略降低了用户决策成本。
- **不依赖 LiteLLM 等中间件**：很多多 LLM 项目会引入 LiteLLM 这种统一适配库。cc-mirror 完全不用——靠"provider 兼容协议 + 改 base_url"足够了。这是"用最少的东西解决问题"的工程哲学。
- **MIT 协议**：可商用、可派生，比 OMC 的 AGPL-3.0 友好得多。
- **关联项目（`Related Projects`）**：tweakcc（主题）、Claude Code Router（路由）、n-skills（技能库）。说明这是一个"小生态"中的一环，专注做好一件事，其他能力交给生态伙伴。
