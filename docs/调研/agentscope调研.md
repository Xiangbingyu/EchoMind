# AgentScope 框架调研报告

> 调研时间：2026-06-05  
> 版本：AgentScope v2  
> 调研目的：评估其用于工作型 AgentHub 的可行性

---

## 一、框架概览

AgentScope 是阿里巴巴（ModelScope 团队）开源的多 Agent 编排框架，当前已演进至 **v2 版本**（2025 年重大架构升级）。

核心定位是 "Agent-Oriented Programming"，以**消息传递（Message）**为核心通信机制，面向开发者提供从单 Agent 到大规模多 Agent 协作的完整解决方案。

- GitHub：https://github.com/agentscope-ai/agentscope
- 官网：https://agentscope.io
- 文档：https://docs.agentscope.io/v2/quickstart

---

## 二、核心组件

### 2.1 Agent

Agent 是 AgentScope 的核心抽象，是一个**无状态的 Reasoning-Acting 循环引擎**，集成了：

- 模型调用（Model）
- 工具调用（Tools / MCP）
- 上下文管理（Context）
- 记忆（Memory）
- Human-in-the-loop
- 中间件（Middlewares）
- 状态管理（State/Session Management）
- 事件系统（Event System）

开箱即用的实现类是 `ReActAgent`，支持 ReAct 循环、结构化输出、并行工具调用、流式响应、实时中断等。

```python
from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel
from agentscope.tool import Toolkit

agent = ReActAgent(
    name="assistant",
    model=DashScopeChatModel(config_name="qwen-max", model_name="qwen-max"),
    memory=InMemoryMemory(),
    toolkit=Toolkit([]),
    sys_prompt="You are a helpful assistant.",
)

msg = Msg(name="user", content="Hello!", role="user")
response = await agent.reply(msg)
```

### 2.2 Message

Message 是 AgentScope 的**基础数据载体**，在 Agent 间通信、UI 展示、Memory 存储、LLM API 交互中均作为统一媒介。

```python
from agentscope.message import Msg, TextBlock

# 文本消息
msg = Msg(name="user", content="请分析这段代码", role="user")

# 多模态消息
msg = Msg(name="user", content=[TextBlock(type="text", text="请分析")], role="user")
```

### 2.3 Memory

分两层：

| 类型 | 说明 | 持久化 |
|------|------|--------|
| 短期记忆（InMemoryMemory） | 当前会话的对话历史，支持压缩摘要 | 依赖 Session 管理 |
| 长期记忆 | 跨会话的用户偏好与知识，集成 Mem0/ReMe | 自动持久化 |

Memory 的 Context 结构：
- **Summary**：较早消息的压缩摘要（发生压缩后出现）
- **Context**：近期未压缩的消息

### 2.4 Tools & Toolkit

工具分三个层次：

- **Tool**：实现 `ToolBase` 接口的单个工具，包括内置工具和 `FunctionTool`/`MCPTool` 适配器
- **Toolkit**：工具容器，向 LLM 暴露 JSON Schema，调度工具调用
- **Tool Group**：命名工具包，Agent 可在运行时动态启用/禁用

内置工具包括 `execute_python_code`、`execute_shell_command`、文件读写等。

```python
from agentscope.tool import Toolkit, FunctionTool

def my_search(query: str) -> str:
    """Search for information."""
    return f"Result for: {query}"

toolkit = Toolkit([FunctionTool(my_search)])
```

### 2.5 Pipeline（多 Agent 编排）

```python
from agentscope.pipeline import MsgHub, sequential_pipeline, fanout_pipeline

# MsgHub：广播模式，所有参与者互相可见消息
async with MsgHub([agent_a, agent_b, agent_c]) as hub:
    await agent_a.reply(user_msg)

# sequential_pipeline：顺序链
result = await sequential_pipeline([agent_a, agent_b], input_msg)

# fanout_pipeline：扇出，同一输入并行分发给多个 Agent
results = await fanout_pipeline([agent_a, agent_b], input_msg)
```

---

## 三、多 Agent 协作机制

AgentScope v2 支持三种核心协作模式：

### 3.1 Routing（路由模式）

路由 Agent 分析输入，通过**结构化输出**（Pydantic BaseModel）决定转发给哪个专业 Agent。

```python
from pydantic import BaseModel, Field
from typing import Literal

class RouteDecision(BaseModel):
    target: Literal["code_agent", "research_agent", "qa_agent"]
    reason: str = Field(description="Routing reason")
```

### 3.2 Handoffs（移交模式）

基于**状态驱动**的路由，Agent 通过工具调用更新 `active_agent` 状态变量，图根据此变量路由到不同 Agent。适合需要明确角色切换的场景（客服转接、任务移交等）。

### 3.3 MsgHub（广播/讨论模式）

多 Agent 共享一个消息广播空间，任何一个 Agent 发出消息，所有其他参与者通过 `observe()` 方法接收。适合多 Agent 讨论、协作写作。

---

## 四、与主流框架对比

| 维度 | AgentScope | LangGraph | AutoGen | CrewAI |
|------|-----------|-----------|---------|--------|
| 核心抽象 | Agent + Message | 状态图节点 | 对话式 Agent | 角色制 Crew |
| 编排模型 | Pipeline/Routing/Handoffs/Hub | 有向图（状态机） | 对话式协作 | 角色分工 |
| 生产就绪度 | 高（v2 大规模升级） | 极高 | 进入维护模式（2025/10） | 中高 |
| 代码执行 | 内置 | 需自行集成 | 内置 | 需插件 |
| MCP 支持 | 完整支持 | 部分 | 部分 | 部分 |
| 并发/并行 | asyncio 原生 | 支持 | 支持 | 支持 |
| Human-in-the-loop | 原生支持（实时中断） | 支持（checkpoint） | 支持 | 支持 |
| 大规模仿真 | 专门优化（万级 Agent） | 不适合 | 不适合 | 不适合 |
| 生态/社区 | 阿里系，中文友好 | LangChain 生态 | Microsoft 生态 | 独立生态 |
| 当前状态 | 活跃开发 | 活跃 | 维护模式 | 活跃 |

**关键差异点：**
- LangGraph 更适合需要严格状态机、可观测性要求高的生产系统
- AgentScope 在大规模 Agent 仿真、MCP 集成、代码执行方面更完整
- AutoGen 已于 2025 年 10 月进入维护模式

---

## 五、与 ACP 协议层集成

AgentScope 在协议层的覆盖较为全面：

| 协议 | 支持情况 |
|------|---------|
| MCP（Model Context Protocol） | 完整支持，`MCPTool` 适配器，有状态/无状态客户端 |
| AG-UI Protocol | 支持，用于 Agent 与前端通信 |
| A2A（Agent-to-Agent，Google） | 通过 Nacos A2A Registry 实现跨语言跨框架互操作 |
| AgentScope Runtime Protocol | 自有 JSON 协议，"Agent as API" 模式 |

关于 **ACP（BeeAI/IBM 的 Agent Communication Protocol）**：ACP 定义了基于 RESTful HTTP 的通用 Agent 通信协议，支持 MIME 多部分消息和同步/异步交互。AgentScope 自身的 Runtime 协议与 ACP 在理念上高度一致，可通过以下方式结合：

1. 将 AgentScope Agent 通过 AgentScope Runtime 暴露为标准 HTTP API 端点
2. 在 ACP 的消息信封层包装 AgentScope 的消息格式
3. 利用 Nacos A2A Registry 实现跨框架发现与调用

---

## 六、针对 EchoMind AgentHub 场景的适配评估

项目技术栈：**Python + SQLite + AgentScope + ACP**，桌面工作型 AgentHub

| 场景需求 | AgentScope 支持情况 | 备注 |
|---------|-------------------|------|
| 单 Agent 工作对话 | 完全支持 | `ReActAgent` 开箱即用，含记忆、工具调用 |
| 多 Agent 协作（Orchestrator 拆解任务） | 完全支持 | Routing + Handoffs + Pipeline 组合使用 |
| 多会话并行 | 完全支持 | asyncio 原生，Session/State 管理模块 |
| @指令进行 Agent 路由 | 需自行实现解析层 | Routing 模式配合结构化输出，解析 @mention 后路由 |
| 代码执行 | 内置支持 | `execute_python_code`、`execute_shell_command` 均为内置工具 |
| 工具调用 | 完整支持 | FunctionTool、MCP、内置工具全覆盖 |
| SQLite 持久化 | 需自行集成 | Memory 接口可扩展，Session 管理可对接 SQLite |
| 与 ACP 结合 | 协议兼容，需适配层 | AgentScope Runtime 协议与 ACP 设计理念一致 |

### 主要局限性

1. **@mention 路由**：框架本身不内置 @mention 解析，需在应用层实现解析逻辑后调用 Routing 机制
2. **SQLite 持久化**：Memory 模块默认是内存级或外部向量库，需自行扩展 Memory 接口适配 SQLite
3. **桌面端集成**：更面向服务端/API 模式，桌面应用需通过 AgentScope Runtime（本地 HTTP 服务）或直接作为 Python 库嵌入
4. **v2 仍在快速迭代**：API 稳定性需关注 breaking changes

---

## 七、推荐架构草图

```
桌面应用层（Python UI / Tauri）
    ↓ @mention 解析 → Agent 路由
AgentScope Pipeline 层
    ├── OrchestratorAgent（ReActAgent + 路由工具）
    │       ↓ Routing / Handoffs
    ├── WorkAgent_A（代码执行）
    ├── WorkAgent_B（文档处理）
    └── WorkAgent_C（搜索/研究）
Memory 层
    ├── InMemoryMemory（当前会话上下文）
    └── SQLite 扩展（跨会话持久化）
协议层
    └── ACP HTTP 端点（AgentScope Runtime 暴露）
```

---

## 八、结论

AgentScope v2 **整体适合**工作型 AgentHub 场景，核心优势：

- asyncio 原生支持多会话并行，无阻塞
- ReActAgent + Toolkit 覆盖代码执行与工具调用
- Pipeline / Routing / Handoffs 三种模式可组合实现 Orchestrator 协调
- 与 ACP 协议在设计上高度兼容
- 阿里系生态，中文文档友好

**需要自行实现的部分：**
- @mention 解析层（工作量小）
- SQLite Memory 适配器（工作量小）

如果对状态机精确控制要求极高、且有 LangSmith 级别可观测性需求，可考虑 LangGraph，但引入复杂度更高。对于桌面工作型应用，AgentScope 的轻量化嵌入方式更为合适。

---

## 参考资料

- [AgentScope 官网](https://agentscope.io/)
- [AgentScope v2 Quickstart](https://docs.agentscope.io/v2/quickstart)
- [AgentScope Agent 文档](https://doc.agentscope.io/tutorial/task_agent.html)
- [AgentScope Pipeline 文档](https://doc.agentscope.io/tutorial/task_pipeline.html)
- [AgentScope Routing 文档](https://doc.agentscope.io/tutorial/workflow_routing.html)
- [AgentScope Handoffs 文档](http://doc.agentscope.io/tutorial/workflow_handoffs.html)
- [AgentScope Tool 文档](https://docs.agentscope.io/v2/building-blocks/tool)
- [AgentScope Runtime Protocol](https://runtime.agentscope.io/en/protocol.html)
- [AgentScope GitHub](https://github.com/agentscope-ai/agentscope)
- [AgentScope 论文（ArXiv）](https://arxiv.org/abs/2402.14034)
- [Agent 协议综述（MCP/ACP/A2A/ANP）](https://arxiv.org/html/2505.02279v1)
- [Nacos A2A Registry with AgentScope](https://www.alibabacloud.com/blog/nacos-a2a-registry-agentscope-enables-cross-language-and-cross-framework-interoperability_602821)
