# 后端架构设计文档

**日期：** 2026-06-06
**范围：** EchoMind AgentHub 第一期后端架构

---

## 一、整体架构

采用 **FastAPI 网关 + AgentScope 独立服务** 方案，两个进程职责分离，本地同机运行，远端部署时可分别扩展。

```
┌─────────────────────────────────────────────┐
│              桌面端 (Electron/Tauri)          │
│  IM UI  │  Workspace管理  │  Diff/Preview    │
└─────────────────┬───────────────────────────┘
                  │ REST + WebSocket
┌─────────────────▼───────────────────────────┐
│           API Gateway (FastAPI)              │
│  /api/*  │  WS /ws/session/{id}             │
│  Auth    │  Session管理  │  Workspace管理    │
│  SQLite（唯一持有层）                         │
└──────────┬──────────────┬────────────────────┘
           │ HTTP（内部）  │ 直接调用
┌──────────▼──────┐  ┌────▼─────────────────┐
│  Agent Service  │  │    Git Service        │
│  (AgentScope)   │  │  (gitpython/内部模块) │
│  Orchestrator   │  │  Proposal Branch      │
│  Agent 实例池   │  │  Branch Lock          │
│  Memory/Context │  │  Version History      │
└─────────────────┘  └───────────────────────┘
```

- **API Gateway**：处理所有客户端请求，维护 WebSocket 连接，唯一访问 SQLite 的层，将 Agent 任务转发给 Agent Service
- **Agent Service**：专注 AgentScope 编排，无状态，通过回调把流式结果推回 Gateway
- **Git Service**：封装 Git 操作，作为内部模块被 Gateway 调用，不直接面向客户端

**本地部署：** 两个进程同机运行，Agent Service 监听 `localhost:8001`
**远端部署：** Agent Service 单独部署，Gateway 通过环境变量 `AGENT_SERVICE_URL` 配置

---

## 二、数据模型

核心五张表：

```sql
workspace
  id, name, endpoint, is_remote, config_json, created_at
  -- endpoint: 本地时为 null，远端时为服务地址（如 http://192.168.1.10:8000）

project_workspace
  id, workspace_id, name, local_path, remote_path, created_at

session
  id, project_workspace_id, type (group/single/group_dm),
  title, created_at, last_active_at

message
  id, session_id, role (user/agent/system), agent_id,
  content, content_type (text/diff/preview/deploy/log),
  created_at

agent
  id, name, type (single/orchestrator/code/doc/test/review),
  skills_json, tools_json, plugins_json, created_at
```

关键约束：
- 群聊 session 与 Project Workspace 1:1 绑定
- `message.content_type` 区分普通文本与结构化内容，前端按类型渲染
- `workspace.is_remote` 标记运行空间是本地还是远端

---

## 三、模块划分

```
backend/
├── gateway/              # FastAPI，REST + WebSocket
│   ├── api/              # 路由：workspace, project, session, message, agent
│   ├── ws/               # WebSocket 连接管理，消息推送
│   ├── db/               # SQLite ORM (SQLAlchemy)
│   └── models/           # 数据模型
│
├── agent_service/        # AgentScope 编排服务（独立进程）
│   ├── orchestrator/     # Orchestrator 角色，Plan 维护，任务调度
│   ├── agents/           # CodeAgent, DocAgent, TestAgent, ReviewAgent
│   ├── memory/           # Context 压缩 + Mem0 长期记忆
│   └── sandbox/          # 本地 Sandbox 管理，进程隔离
│
└── git_service/          # Git 操作封装（gateway 内部模块）
    ├── repo/             # 内部接口：initRepository, createProposalBranch 等
    └── api/              # 对外接口：供 gateway 路由层调用
```

---

## 四、通信与数据流

### REST 主要端点

```
# Workspace / Project
POST   /api/workspaces
POST   /api/workspaces/{id}/projects

# Session / Message
POST   /api/sessions
GET    /api/sessions/{id}/messages

# Git / Proposal
POST   /api/projects/{id}/repo/init
POST   /api/projects/{id}/proposals
GET    /api/projects/{id}/proposals
GET    /api/proposals/{id}/diff
POST   /api/proposals/{id}/commit
POST   /api/proposals/{id}/confirm
POST   /api/projects/{id}/push
GET    /api/projects/{id}/history
```

### WebSocket

```
WS /ws/session/{session_id}
```

实时事件类型：

```json
{ "type": "agent.token",    "data": "..." }
{ "type": "agent.done",     "data": {...} }
{ "type": "task.status",    "data": "running" }
{ "type": "proposal.ready", "data": {...} }
{ "type": "sandbox.log",    "data": "..." }
```

### Agent 执行流

```
客户端发消息
  → gateway 写入 message 表
  → gateway HTTP POST → agent_service /run
  → AgentScope 执行，流式回调 → gateway
  → gateway 通过 WS 推给客户端
  → 执行完成，gateway 写入结果 message
```

---

## 五、Session 与 Memory 架构

直接使用 AgentScope 原生能力，无需自研。

### 短期上下文（AgentScope Context）

```
head messages  →  保留（稳定系统信息）
middle         →  AgentScope 自动压缩成 summary
tail messages  →  保留（最近活跃消息）
```

压缩后上下文结构：
```
system / stable context
→ head messages
→ compression summary
→ tail messages
```

### 长期记忆

- **mem0**：用户偏好、项目规则、跨 session 重要事实，通过 AgentScope 原生 `Mem0LongTermMemory` 集成
- **memory.md**：关键稳定记忆，存于 Project Workspace 目录下，通过 memory tool 由模型主动写入

### 群聊 Session 隔离规则

- 群聊主线程、群内单聊、普通单聊各自独立 session
- 群内单聊的 Agent 可读取所属群聊的 session 历史，但只读，不写入
- 只有用户显式转发后，群内单聊内容才进入群聊历史

---

## 六、Sandbox 执行模型

- Sandbox 跑在**用户本地**（临时进程/目录），基于 Project Workspace 快照创建
- Agent 在本地 Sandbox 中编码、测试，产出 Proposal
- Commit 时才将改动推送到 Project Workspace 真实环境（本地目录或远端服务器）
- 任务完成后 Sandbox 自动销毁，避免环境污染

---

## 七、Orchestrator 与多 Agent 协作

- **Orchestrator** 作为群聊主 Agent，维护 Plan 状态对象，负责任务拆解、调度、进度跟踪
- 每个子任务完成后触发 Orchestrator check → redispatch（正常）或 replan（计划失效时）
- 子 Agent：CodeAgent、DocAgent、TestAgent、ReviewAgent，可通过 `@` 直接唤醒或由 Orchestrator 指派
- Agent 能力通过 skills/tools/plugins 装配，不写死

---

## 八、技术选型汇总

| 层 | 选型 |
|---|---|
| API Gateway | FastAPI + uvicorn |
| WebSocket | FastAPI WebSocket |
| ORM | SQLAlchemy + aiosqlite |
| Agent 编排 | AgentScope |
| 上下文压缩 | AgentScope Context（内置） |
| 长期记忆 | AgentScope Mem0LongTermMemory |
| Git 操作 | gitpython |
| 进程通信 | HTTP（内部 REST） |
| 存储 | SQLite（Gateway 层） |

---

## 九、本期不实现

- 分段 session / session_summary RAG
- 完整企业级权限体系
- 复杂云端调度和大规模分布式执行
- Docker/容器化 Sandbox（一期只做本地进程沙箱）
