# AgentScope 沙盒、Workspace 与协调器调研

> 调研时间：2026-06-05  
> 版本：AgentScope v2

---

## 一、沙盒（Sandbox）

### 核心结论

AgentScope 沙盒能力分为两个完全不同的层次，必须区分清楚：

**核心库（agentscope）：不安全，没有真正沙盒**

`execute_python_code` 和 `execute_shell_command` 位于 `src/agentscope/tool/_coding/_python.py`，对输入参数缺乏校验和沙盒隔离，直接在宿主进程中 `exec` 代码。已披露 RCE 漏洞（CVE-2026-6603 / SNYK-PYTHON-AGENTSCOPE-16318344）。**生产环境不能直接使用**。

**AgentScope Runtime（独立包）：真正的沙盒**

`agentscope-runtime` 是独立的生产级运行时，提供三种后端：

| 后端 | 适用场景 |
|------|---------|
| 本地进程隔离 | 开发/测试 |
| Docker 容器 | 本地生产 |
| E2B 云沙盒 | 云端执行 |

支持远程沙盒服务器模式，可将沙盒部署为独立服务，通过 SDK 连接。沙盒内可见的文件系统由 `WorkspaceSpec` + workspace projection 机制定义（将宿主特定路径 mount/sync 到沙盒内）。

### 对 EchoMind 的影响

- 第一期如需代码执行，**必须使用 agentscope-runtime**，不能直接用核心库的 `execute_python_code`
- Docker 沙盒后端与第一期"Sandbox 容器"概念完全吻合，可直接对应

---

## 二、Workspace（工作空间）

### 核心概念

AgentScope v2 有正式的 Workspace 支持（[官方文档](https://docs.agentscope.io/v2/building-blocks/workspace)）。

**三种实现后端：**

| 实现 | 说明 |
|------|------|
| Local Filesystem | 宿主机本地目录 |
| Docker Container | 容器内隔离文件系统 |
| E2B Cloud Sandbox | 云端沙盒文件系统 |

**WorkspaceManager**：在多租户/多会话场景下，`WorkspaceManager` 负责分配和追踪 Workspace，可以按用户、按 Agent 或按 Session 映射不同的 Workspace，Agent 代码本身无需改动。

**多 Agent 共享工作空间**：多个 Agent 可共享同一个 Workspace 目录（通过 WorkspaceManager 分配相同路径），实现文件级别的状态共享。

### 局限性

- 并发写入冲突没有内置锁机制
- 细粒度文件权限控制（哪个 Agent 能读写哪些文件）文档未明确
- Python v2 与 Java 版本的 Workspace API 是否完全对齐尚不确定

### 对 EchoMind 的影响

AgentScope 的 Workspace 概念与 EchoMind 的 Workspace 设计高度吻合，可以直接映射：
- EchoMind Workspace → AgentScope Workspace（Local/Docker 后端）
- EchoMind 多 Session 隔离 → WorkspaceManager 多租户分配

---

## 三、Orchestrator（协调器）

### 核心结论

AgentScope **没有内置的 `OrchestratorAgent` 专用类**，而是通过以下四种机制组合实现协调：

**a) HarnessAgent Subagent 机制**（最接近 Orchestrator 的抽象）

父 Agent 通过调用 `Task` 工具委派子任务给临时子 Agent 实例：

```
父 HarnessAgent（扮演 Orchestrator）
  ├── 调用 Task(subagent_type="ResearchAgent", task="搜集资料...")
  ├── 调用 Task(subagent_type="CodeAgent", task="实现功能...")
  └── 汇总结果 → 返回用户
```

子 Agent 是临时的 HarnessAgent 实例，拥有独立的 sub-session，结果以 tool output 形式返回给父 Agent，支持并行调用。

**b) Routing 模式**

ReActAgent 作为路由节点，通过结构化输出（Pydantic BaseModel）决定将消息路由到哪个下游 Agent：

```python
class RouteDecision(BaseModel):
    target: Literal["code_agent", "research_agent", "qa_agent"]
    reason: str
```

**c) Task Pipeline**

`agentscope.pipeline` 提供有向图式的任务编排，支持顺序、并行、条件 pipeline，适用于结构固定的多步骤工作流。

**d) Handoffs 模式**

Agent 间的显式控制权转交，类似 OpenAI Swarm，适合对话流中的动态角色切换。

### 任务拆解（Task Decomposition）的实现路径

AgentScope **没有内置的自动任务拆解模块**，任务拆解依赖：
1. 父 Agent 的 LLM 推理能力（ReAct 循环中自主判断子任务）
2. 开发者在 sys_prompt 中显式描述拆解策略
3. Pipeline 硬编码拆解逻辑（结构固定时）

### 局限性

- 无专门的 Planner/Orchestrator Agent 类型，需开发者自行封装
- 任务拆解是隐式的（依赖 LLM 判断），不如 LangGraph 的显式状态机可控
- 子任务并行执行需手动管理 async/await，无自动并行调度器
- 结果汇总无内置 aggregator，父 Agent 通过 prompt 自行合并

---

## 四、总结

| 功能 | 成熟度 | 核心能力 | 主要短板 |
|------|--------|---------|---------|
| Sandbox | 核心库不安全，Runtime 完善 | Docker/E2B 隔离，远程沙盒服务器 | 需单独部署 agentscope-runtime |
| Workspace | v2 正式支持 | 三后端 + WorkspaceManager 多租户 | 并发控制、权限控制文档缺失 |
| Orchestrator | 有能力，无专用抽象 | HarnessAgent subagent + Pipeline + Routing | 无内置 Planner，任务拆解依赖 LLM prompt |

---

## 参考资料

- [AgentScope Runtime Sandbox](https://runtime.agentscope.io/en/api/sandbox.html)
- [AgentScope v2 Workspace 文档](https://docs.agentscope.io/v2/building-blocks/workspace)
- [AgentScope Java Subagent 文档](https://java.agentscope.io/en/multi-agent/subagent.html)
- [AgentScope Task Pipeline 文档](https://doc.agentscope.io/tutorial/task_pipeline.html)
- [CVE-2026-6603 RCE 漏洞](https://www.sentinelone.com/vulnerability-database/cve-2026-6603/)
