# AgentScope v2 功能全景清单

> 调研时间：2026-06-05  
> 版本：AgentScope v2（2025 年重大架构升级）  
> 注：标注 (Java) 的功能为 AgentScope Java 子项目特有；v2 相较 v1 是 Breaking Release

---

## 一、核心能力

### Agent 类型

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| 统一 `Agent` 类 | 原生支持 | v2 将旧版 ReActAgent 重构为单一统一类，无状态推理-行动循环引擎 |
| ReActAgent（旧称） | 已并入 Agent | v1 独立类，v2 合并入统一 `Agent`，逻辑不变 |
| HarnessAgent | 原生支持 (Java) | 在 ReAct 基础上注入工作区管理、记忆持久化、上下文压缩，通过 Hooks 实现 |
| Realtime Agent | 原生支持 | 支持实时音视频/语音交互场景 |
| 自定义 Agent | 原生支持 | 继承 `Agent` 基类，覆写 `reply` / `reply_stream` 方法 |

---

### 模型支持

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| DashScope（阿里云 Qwen 系列） | 原生支持 | 原生 HTTP 调用，无需额外 SDK |
| OpenAI 系列（GPT-4o 等） | 原生支持 | `OpenAIChatModel` |
| OpenAI 兼容 API（vLLM、DeepSeek 等） | 原生支持 | `OpenAIChatModel` + 自定义 `base_url` |
| 本地模型（Ollama、vLLM 等） | 需配置 | 通过 OpenAI 兼容接口对接 |
| 多模态模型（图像/音频/视频） | 原生支持 | `DataBlock` 统一媒体块 |
| TTS 模型 | 原生支持 | 统一接口跨多个 TTS 提供商 |
| Embedding 模型 | 原生支持 | `DashScopeMultiModalEmbedding` 支持文本/图像/视频多模态嵌入 |
| Credential 凭证管理 | 原生支持 | 先注册 Credential，再获取该 provider 支持的模型列表 |
| 模型微调（Tuner） | 原生支持 | v2 内置 Tuner，支持模型 finetuning |
| 故障回退（Failover） | 原生支持 | provider 瞬时故障自动回退 |

---

### 消息系统（Msg & Event）

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| `Msg` 消息结构 | 原生支持 | 含 sender、role、content（typed blocks）、metadata、UUID、timestamp |
| `TextBlock` | 原生支持 | 纯文本内容块 |
| `DataBlock`（统一媒体块） | 原生支持 | v2 将 ImageBlock/AudioBlock/VideoBlock 统一为 DataBlock，通过 `media_type` 区分 |
| `HintBlock` | 原生支持 | Agent 引导与中间推理提示块（v2 新增） |
| `ToolCallBlock` / `ToolResultBlock` | 原生支持 | 工具调用与结果的结构化块 |
| 多模态消息 | 原生支持 | 通过 DataBlock 携带图像/音频/视频 |
| Pydantic 序列化/验证 | 原生支持 | 所有 content blocks 继承自 Pydantic BaseModel |
| Event 事件流 | 原生支持 | 每个 Agent 步骤均作为 typed event 可观测（text token、tool call、tool result、permission request） |
| `reply()` 同步接口 | 原生支持 | 同步返回最终消息 |
| `reply_stream()` 流式接口 | 原生支持 | 流式逐步产出 typed events，支持实时 UI 和 HITL |

---

### 记忆与上下文管理

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| 短期记忆（InMemoryMemory） | 原生支持 | 当前会话对话历史，依赖 Session 持久化恢复 |
| 长期记忆 | 原生支持 | 跨 session 存储用户偏好，通过 Mem0/ReMe 持久化 |
| 上下文自动压缩 | 原生支持 | 长对话自动维持在上下文窗口内 |
| Context Offloading（上下文卸载） | 原生支持 | 将压缩移除的内容持久化到外部存储，后续可检索；通过 `Offloader` 接口 |
| Tablestore 持久化记忆 | 原生支持 | 阿里云 Tablestore 实现分布式持久化与可搜索记忆 |
| SQLite FTS5 全文搜索 | 原生支持 (Java) | Harness 层集成 SQLite FTS5 全文检索 |
| 双层记忆架构（每日日志 + 长期记忆） | 原生支持 (Java) | 高频低整理日志 + 低频高整理长期记忆，自动后台维护 |

---

### 工具系统

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| `FunctionTool`（自定义工具） | 原生支持 | 将 Python 函数包装为工具，自动提取 docstring 作为描述 |
| `MCPTool` | 原生支持 | 将 MCP 服务器工具注册为 Agent 工具 |
| Skill（动态技能） | 原生支持 | 运行时可动态添加/移除的技能单元，归属 Workspace |
| Tool Group（工具分组） | 原生支持 | 命名工具包，运行时通过内置 meta tool 动态激活/停用 |
| 工具并发执行 | 原生支持 | 多工具步骤并发完成，加速推理 |
| 内置：`execute_python_code` | 原生支持（核心库有 RCE 风险） | 执行 Python 代码；生产环境须用 agentscope-runtime 沙箱版 |
| 内置：`execute_shell_command` | 原生支持（核心库有 RCE 风险） | 执行 Shell 命令；同上 |
| 内置：文本文件读写 | 原生支持 | `text_file_read` / `text_file_write` |
| 内置：Search / RAG / AIGC / Payments | 原生支持 (Runtime) | agentscope-runtime 预置工具，开箱即用 |
| 内置：记忆/会话搜索、子 Agent 委托 | 原生支持 (Java) | Harness 层开箱即用 |
| 结构化输出 | 原生支持 | 所有 content blocks 基于 Pydantic，支持类型验证与序列化 |

---

## 二、多 Agent 编排

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| Sequential Pipeline（顺序管道） | 原生支持 | A → B → C 固定顺序 |
| Parallel Pipeline（并行管道） | 原生支持 | 相同输入分发给多个 Agent，结果合并 |
| Loop Pipeline（循环管道） | 原生支持 | 重复执行子管道直到满足条件 |
| Custom Workflow（自定义工作流） | 原生支持 | 完整图结构：顺序/条件分支/循环/并行，节点可为确定性/LLM-based/Agentic |
| Routing（路由模式） | 原生支持 | 通过结构化输出决定路由到哪个专业 Agent |
| Handoffs（移交模式） | 原生支持 | Agent 间显式控制权转交，类似 OpenAI Swarm |
| MsgHub（广播模式） | 原生支持 | 任一 Agent 发消息，其他参与者通过 `observe()` 接收 |
| Subagent / Task Delegation | 原生支持 | 父 Agent 通过 Task 工具委派子任务给独立子 Agent，支持并行 |
| HarnessAgent Subagent | 原生支持 (Java) | Harness 层内置子 Agent 委派，防止主线程上下文膨胀 |

---

## 三、运行时与部署

### AgentScope Runtime（独立包）

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| 生产级运行时框架 | 原生支持 | 独立包 `agentscope-runtime`，提供安全沙箱、Agent-as-a-Service、全栈可观测性 |
| "Agent as API" 模式 | 原生支持 | 本地开发到生产部署统一的 API 封装体验 |
| 多框架兼容（LangGraph、Agno、AutoGen） | 需配置 | 通过 Integration Guide 对接其他框架 |
| 预置工具集（Search/RAG/AIGC/Payments） | 原生支持 | Runtime 内开箱即用 |

### 沙盒（Sandbox）

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| 本地进程隔离 | 原生支持 (Runtime) | 开发/测试用 |
| Docker 容器沙盒 | 原生支持 (Runtime) | 生产级代码执行隔离 |
| E2B 云沙盒 | 原生支持 (Runtime) | 云端执行环境 |
| 远程沙盒服务器模式 | 原生支持 (Runtime) | 沙盒部署为独立服务，通过 SDK 连接 |
| 核心库直接执行（不安全） | 可用但有 RCE 漏洞 | CVE-2026-6603，生产环境禁止直接使用 |

### Workspace 系统

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| 本地文件系统 Workspace | 原生支持 | 默认本地工作目录 |
| Docker Workspace | 原生支持 | 一行配置切换到 Docker 容器 |
| E2B Cloud Workspace | 原生支持 | 一行配置切换到 E2B 云沙盒 |
| WorkspaceManager（多租户） | 原生支持 | 按用户/Agent/Session 分配隔离的 Workspace |
| MCP clients 与 Skills 隔离 | 原生支持 | 每个 Workspace 的 MCP 客户端和技能独立隔离 |
| SessionTree（JSONL 双文件会话树） | 原生支持 (Java) | 支持压缩卸载的持久化会话树结构 |

### Session 与状态管理

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| Session 状态管理 | 原生支持 | Agent Service 管理 per-user session 状态与持久化 |
| Session 持久化与恢复 | 原生支持 | 短期记忆依赖 Session 实现跨调用恢复 |
| AgentState 显式状态管理 | 原生支持 | v2 新增，替代旧版隐式 `state_dict` / `load_state_dict` |

### Human-in-the-Loop

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| 工具调用前暂停确认 | 原生支持 | Agent 调用工具前暂停，等待用户确认后继续 |
| 运行中编辑工具参数 | 原生支持 | 用户可在运行中修改工具参数后继续 |
| 敏感操作移交自定义后端 | 原生支持 | 敏感操作可交给用户自己的后端处理，Agent 在原位恢复 |
| Permission 请求通过 Event Stream 传递 | 原生支持 | 权限确认请求作为 typed event 传递，驱动前端 UI |

---

## 四、协议与集成

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| MCP 客户端（Stateful） | 原生支持 | 有状态客户端，手动管理 connect/close，持久会话 |
| MCP 客户端（Stateless） | 原生支持 | 无状态客户端，每次调用自动管理连接 |
| MCP 工具注册为 Agent 工具 | 原生支持 | MCP 服务器工具自动包装为可用工具 |
| MCP 与 Workspace 隔离 | 原生支持 | MCP 客户端生命周期属于 Workspace，per-session 隔离 |
| Nacos MCP 服务发现 | 需配置 (Java) | 通过 Nacos 注册中心自动发现 MCP/A2A 服务 |
| AG-UI 协议（前后端通信） | 原生支持 | Event Stream 直接兼容 AG-UI，无需手写适配器 |
| A2A（Agent-to-Agent）协议 | 原生支持 | 获取 Agent Card、连接远程 Agent；Event Stream 直接兼容 A2A |
| BeeAI/IBM ACP 协议 | 未确认原生支持 | 官方文档未明确，Runtime 协议规范可能有所涉及 |
| Agent Service API Server | 原生支持 | 完整模块化 API 服务（路由/Session/持久化/调度），认证/存储/聊天协议均可插拔 |
| Agent API Protocol | 原生支持 (Runtime) | 完整 Agent API 协议规范，支持多模态内容、MCP 工具列表查询 |

---

## 五、观测与调试

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| AgentScope Studio（可视化界面） | 原生支持 | Web 界面，实时可视化 Agent 执行、消息追踪、交互调试 |
| Token 用量 / 模型调用统计 | 原生支持 | Studio 中集中查看 |
| OpenTelemetry Tracing | 原生支持 | `agentscope.init(tracing_url=...)` 配置 OTLP 端点 |
| 装饰器式 Tracing（`@trace`） | 原生支持 (Runtime) | 追踪函数执行 |
| Context Manager 式 Tracing | 原生支持 (Runtime) | `with trace():` 追踪代码块 |
| Event Stream 可观测性 | 原生支持 | 每步产出 typed event：text/thinking/tool call/tool result |
| Tracing 通过 Middleware 注入 | 原生支持 | v2 已将 OpenTelemetry 从 agent class 移出，改由 Middleware 注入 |

---

## 六、扩展与架构

### 权限系统

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| 工具调用三态决策（allow/deny/ask） | 原生支持 | 拦截每次工具调用，静态配置 + 动态运行时分析 |
| Permission 请求通过 Event Stream 传递 | 原生支持 | 权限确认请求作为 typed event 驱动前端 UI |

### 中间件（Middlewares）

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| Agent Middleware 系统 | 原生支持 | v2 新增，替代旧版 Hook 机制，在执行管道关键点注入自定义逻辑 |
| 内置：日志/Tracing/输入改写/访问控制 | 原生支持 | 通过 Middleware 注入，无需修改 agent 或 model 代码 |

### 分布式与大规模仿真

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| Actor-based 分布式机制 | 原生支持 | 底层 actor 架构，本地与分布式部署无缝切换，自动并行优化 |
| 大规模 Multi-Agent 仿真（万级 Agent） | 原生支持 | 专为大规模仿真优化，支持 Agent-Environment 双向交互 |

### RAG / Evaluation

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| RAG（检索增强生成） | 原生支持 | 内置 RAG 功能，Runtime 预置 RAG 工具 |
| Evaluation 评估模块 | 原生支持 | v2 内置评估，集成 OpenJudge |

### 插件/扩展

| 功能 | 支持状态 | 说明 |
|------|----------|------|
| 自定义工具（FunctionTool） | 原生支持 | 任意 Python 函数包装 |
| 自定义 Middleware | 原生支持 | 可插拔注入执行管道 |
| 可插拔 Workspace 策略（Local/Docker/E2B） | 原生支持 | 一行配置切换 |
| 可插拔存储/认证/聊天协议（Agent Service） | 原生支持 | Agent Service 各层均可替换 |
| 自定义 Agent 继承扩展 | 原生支持 | 继承 `Agent` 基类 |
| Skill 动态技能机制 | 原生支持 | 运行时动态添加/移除，归属 Workspace |

---

## 七、v1 → v2 Breaking Changes 摘要

| 变更 | v1 | v2 |
|------|----|----|
| Agent 类型 | `ReActAgent` 独立类 | 统一 `Agent` 类 |
| 媒体块 | `ImageBlock`/`AudioBlock`/`VideoBlock` | 统一 `DataBlock(media_type=...)` |
| 状态管理 | `state_dict` / `load_state_dict` | `AgentState` 显式类型 |
| 可观测性 | OpenTelemetry 内嵌于 agent class | 通过 Middleware 注入 |
| Hook 机制 | `Hook` | `Middleware` |
| 自动迁移 | — | 无，Breaking Release，需手动迁移 |

---

## 参考资料

- [AgentScope v2 What's New](https://docs.agentscope.io/?)
- [AgentScope v2 Building Blocks](https://docs.agentscope.io/v2/building-blocks/agent)
- [AgentScope v2 Change Log](https://docs.agentscope.io/v2/change-log)
- [AgentScope Runtime](https://runtime.agentscope.io/en/intro.html)
- [AgentScope Java](https://java.agentscope.io/en/intro.html)
- [AgentScope GitHub](https://github.com/agentscope-ai/agentscope)
- [Large-Scale Multi-Agent Simulation](https://arxiv.org/abs/2407.17789v2)
