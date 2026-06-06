# QwenPaw 项目 AgentScope 实践分析

> 调研时间：2026-06-05  
> 源码路径：E:\Github\QwenPaw  
> 依赖版本：agentscope==1.0.20，agentscope-runtime==1.1.6

---

## 一、主链路架构

```
用户请求（HTTP / IM 渠道）
    ↓
FastAPI app  ←  AgentApp（agentscope_runtime.engine.app）
    ↓
DynamicMultiAgentRunner          # 根据 X-Agent-Id 请求头动态路由
    ↓
Workspace（per-agent 隔离运行时）
    ↓
AgentRunner.stream_query()       # 流式推理入口
    ↓
QwenPawAgent.reply()             # 继承自 ReActAgent
    ├── _reasoning()             # LLM 推理，产出 tool_use blocks
    ├── _acting()                # 工具执行（含 plan gate 检查）
    └── _summarizing()           # 无工具时生成最终文本
```

### 关键类关系

```python
class QwenPawAgent(CodingModeMixin, ToolGuardMixin, ReActAgent):
    # MRO: QwenPawAgent → CodingModeMixin → ToolGuardMixin → ReActAgent
```

`ReActAgent` 是 AgentScope 的核心 Agent 类，QwenPaw 在其上通过多重继承叠加了：
- `ToolGuardMixin`：工具调用前安全拦截
- `CodingModeMixin`：代码 Diff / LSP / AST 搜索

---

## 二、AgentScope 的具体使用方式

### 1. ReActAgent 初始化

```python
super().__init__(
    name=agent_config.name or "QwenPaw",
    model=model,             # 由 create_model_and_formatter() 创建
    sys_prompt=sys_prompt,
    toolkit=toolkit,         # Toolkit() 注册了所有内置工具和 skills
    memory=InMemoryMemory(), # AgentScope 短期记忆
    formatter=formatter,
    max_iters=running_config.max_iters,
    plan_notebook=plan_notebook,  # 可选，用于 /plan 功能
)
```

### 2. Toolkit 工具注册

内置工具通过 `Toolkit.register_tool_function()` 注册：

```python
toolkit = Toolkit()
toolkit.register_tool_function(execute_shell_command, async_execution=True)
toolkit.register_tool_function(read_file)
toolkit.register_tool_function(write_file)
toolkit.register_tool_function(browser_use)
# ... 共约 20 个内置工具
```

Skills（动态技能）通过 AgentScope v2 的 skill 机制注册：

```python
toolkit.register_agent_skill(str(skill_dir))  # skill_dir 是 skills/<name>/ 目录
```

MCP 工具通过 AgentScope 的 MCP 客户端注册：

```python
await self.toolkit.register_mcp_client(client, namesake_strategy="skip")
```

### 3. 消息系统

完全使用 AgentScope 的 `Msg` 类，并在 `app/runner/utils.py` 中实现转换器将其映射到 agentscope-runtime 的协议格式：

```python
# agentscope_msg_to_message() 处理以下 block 类型：
# text           → TextContent
# thinking       → MessageType.REASONING
# tool_use       → MessageType.PLUGIN_CALL + FunctionCall
# tool_result    → MessageType.PLUGIN_CALL_OUTPUT + FunctionCallOutput
# image/audio/video/file → 对应 media Content 类型
```

### 4. Hook 机制

通过 `register_instance_hook()` 注入生命周期钩子（AgentScope v1/v2 均支持）：

```python
# pre_reply：上下文管理器预处理
self.register_instance_hook("pre_reply", "context_pre_reply", context_manager.pre_reply)
# pre_reasoning：Bootstrap 引导 + 上下文压缩检查
self.register_instance_hook("pre_reasoning", "bootstrap_hook", bootstrap_hook)
self.register_instance_hook("pre_reasoning", "context_pre_reasoning", ...)
# post_acting：工具执行后上下文更新
self.register_instance_hook("post_acting", "context_post_acting", ...)
# post_reply：上下文保存
self.register_instance_hook("post_reply", "context_post_reply", ...)
```

### 5. Session 管理

自定义 `SafeJSONSession` 继承 AgentScope 的 `SessionBase`，重写了文件路径生成和 I/O（Windows 非法字符处理、异步 aiofiles 读写、频道子目录隔离）。

---

## 三、Workspace 的使用

**QwenPaw 实现了完整的自定义 Workspace 系统，未使用 AgentScope Runtime 的原生 Workspace。**

每个 `Workspace` 是一个独立 Agent 运行时，包含以下服务（按启动优先级）：

| 优先级 | 服务 | 说明 |
|--------|------|------|
| 10 | `AgentRunner` | 请求处理核心 |
| 20 | `memory_manager` | 对话记忆（可插拔后端） |
| 20 | `context_manager` | 上下文压缩管理（可插拔后端） |
| 20 | `mcp_manager` | MCP 工具客户端管理 |
| 20 | `chat_manager` | 聊天状态管理 |
| 25 | `runner_start` | Runner 启动 |
| 30 | `channel_manager` | IM 渠道（DingTalk/Discord/Telegram/QQ 等） |
| 40 | `cron_manager` | 定时任务调度 |
| 50 | `agent_config_watcher` | Agent 配置热更新 |
| 51 | `mcp_config_watcher` | MCP 配置热更新 |

**Workspace 目录结构（落盘）：**

```
workspace/<agent_id>/
├── AGENTS.md / SOUL.md / PROFILE.md   # 系统 prompt 来源文件
├── skills/                             # 动态技能
│   └── <skill_name>/SKILL.md
├── sessions/                           # 会话历史（SafeJSONSession）
│   └── <channel>/<session_id>.json
├── chats.json                          # 聊天列表
├── jobs.json                           # 定时任务
└── mcp_config.json                     # MCP 工具配置
```

`MultiAgentManager` 在 app 启动时读取所有已配置的 agent_id，逐一创建 `Workspace` 并调用 `start()`。`DynamicMultiAgentRunner` 根据请求头 `X-Agent-Id` 将请求路由到对应的 Workspace。

---

## 四、Sandbox 的使用

**QwenPaw 没有使用 AgentScope Runtime 的 Docker/E2B 沙盒，而是实现了自己的安全防护层。**

安全防护通过 `ToolGuardMixin` 和 `ToolGuardEngine` 实现，在工具调用前拦截：

```python
class ToolGuardEngine:
    guardians = [
        FilePathToolGuardian,    # 文件路径越权检查（拦截 workspace 外访问）
        RuleBasedToolGuardian,   # 基于规则的命令黑名单
        ShellEvasionGuardian,    # Shell 逃逸检测
    ]
```

另有 `security/skill_scanner/` 对新安装的 Skill 代码进行安全扫描。

---

## 五、多 Agent 功能

QwenPaw 在内置工具中实现了 Agent 间协作，绕过了 AgentScope 的 Pipeline/Handoffs 机制，直接通过工具调用实现：

| 工具 | 说明 |
|------|------|
| `delegate_external_agent` | 委托外部 Agent 执行任务（支持 async_execution） |
| `chat_with_agent` | 与另一个 Agent 对话 |
| `submit_to_agent` | 向 Agent 提交任务 |
| `check_agent_task` | 检查 Agent 任务状态 |
| `spawn_subagent` | 创建子 Agent |
| `list_agents` | 列出可用 Agent |

以上工具配合 `TaskTracker` 实现异步任务追踪，支持 `view_task / wait_task / cancel_task`。

---

## 六、对 EchoMind 的参考价值

| QwenPaw 实践 | EchoMind 可借鉴点 |
|-------------|-----------------|
| `ReActAgent` 继承 + 多重 Mixin | 核心 Agent 设计模式，扩展性强 |
| `Workspace` 作为 per-agent 隔离运行时 | 直接对应 EchoMind 的 Workspace 概念 |
| `SafeJSONSession` 继承 `SessionBase` | Session 持久化的扩展方式 |
| Hook 注入上下文管理 | 上下文压缩/保存的无侵入集成方式 |
| 工具级安全守卫（非容器沙盒） | 第一期可用此方案替代 Docker 沙盒 |
| 内置工具实现多 Agent 协作 | 比 Pipeline/Handoffs 更灵活的 Agent 间通信 |
| `toolkit.register_agent_skill()` | Skill 动态装配的标准用法 |
| `agentscope_msg_to_message()` 转换层 | Frontend 协议与 AgentScope Msg 的解耦模式 |

### 关键发现

1. **AgentScope Runtime 的 Workspace/Sandbox 未被使用**：QwenPaw 全部自行实现，说明 Runtime 的这些功能在实际项目中可选用性较高，不是强依赖
2. **Session 存储自定义**：通过继承 `SessionBase` 轻松替换为 SQLite 等后端，EchoMind 可同样处理
3. **多 Agent 通过工具实现**：不依赖 AgentScope 的 Pipeline，更灵活，适合 EchoMind 的 @mention 路由场景
4. **整体架构**：AgentScope 仅作为"ReAct 推理引擎 + 工具调用框架"使用，上层的 Workspace 管理、路由、会话、渠道全部自行实现
