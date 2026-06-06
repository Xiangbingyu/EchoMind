# ACP 协议调研报告

> 调研时间：2026-06-05  
> 重点：Claude Code、Codex CLI 等工具的接入方式

---

## 一、重要澄清："ACP"指两个不同协议

| 维度 | BeeAI/IBM ACP | Zed ACP（Agent Client Protocol） |
|------|--------------|----------------------------------|
| 全称 | Agent Communication Protocol | Agent Client Protocol |
| 发起方 | IBM Research / BeeAI / Linux Foundation | Zed Industries |
| 传输层 | RESTful HTTP | JSON-RPC 2.0 over stdio |
| 定位 | **Agent ↔ Agent 编排总线** | **编辑器 ↔ Agent 集成协议** |
| 类比 | 微服务间的 HTTP | LSP（语言服务协议）的 Agent 版 |
| 主要用户 | LangChain, CrewAI, 自定义框架 | Zed, VS Code, Cursor |

两者不竞争，可以叠加使用。以下分别展开。

---

## 二、BeeAI/IBM ACP（Agent Communication Protocol）

### 核心规范

- 传输：RESTful HTTP，标准 OpenAPI 规范
- 消息格式：JSON，支持 MIME multipart（文本、图像、音频、自定义类型混合）
- 交互模式：同步（直接返回）、异步（轮询 / SSE 流式）、长任务执行

核心端点：

```
POST /runs              # 同步执行 agent
POST /runs/async        # 异步提交任务
GET  /runs/{run_id}     # 轮询任务状态
GET  /runs/{run_id}/stream  # SSE 流式获取结果
GET  /agents            # 发现可用 agents
```

消息结构：

```json
{
  "agent_name": "my_agent",
  "input": [
    {
      "parts": [
        { "content_type": "text/plain", "content": "分析这段代码" }
      ]
    }
  ]
}
```

### Python ACP SDK

将自定义 Agent 暴露为 ACP 服务：

```python
from acp_sdk.server import Server
from acp_sdk.models import Message, MessagePart

server = Server()

@server.agent()
async def my_code_agent(input: list[Message]) -> Message:
    user_text = input[-1].parts[0].content
    result = await do_coding_task(user_text)
    return Message(parts=[MessagePart(content_type="text/plain", content=result)])

server.run(port=8000)
```

调用其他 ACP Agent：

```python
from acp_sdk.client import Client

async with Client(base_url="http://localhost:8000") as client:
    run = await client.run_sync(agent="my_code_agent", input=[...])
    print(run.output[0].parts[0].content)
```

### Claude Code 与 BeeAI ACP

Claude Code **官方目前不原生支持** BeeAI ACP。接入方式：
- 社区项目 [agentclientprotocol/claude-agent-acp](https://github.com/agentclientprotocol/claude-agent-acp)：将 Claude Agent SDK 包装为 ACP 可调用服务
- 自行用 Python ACP SDK 将 Claude API 调用包装成 ACP Agent server

### Codex CLI 与 BeeAI ACP

OpenAI Codex CLI **不原生支持** BeeAI ACP，同样需要包装适配层，目前无官方支持声明。

---

## 三、Zed ACP（Agent Client Protocol）——编辑器接入协议

这是**更直接关联 Claude Code、Codex CLI 的协议**。

### 核心规范

- 传输：JSON-RPC 2.0 over **stdin/stdout**（类似 LSP 的进程间通信）
- 启动方式：编辑器 fork 一个子进程，通过 stdin/stdout 双向通信
- 设计目标：让"任何编辑器"能接入"任何 AI Agent"（类比 LSP 对语言服务器的标准化）

核心 JSON-RPC 方法：

```json
// 编辑器 → Agent：发送用户请求
{
  "jsonrpc": "2.0",
  "method": "agent/request",
  "params": {
    "thread_id": "abc123",
    "message": "重构这个函数",
    "context": { "files": [...], "selection": {...} }
  }
}

// Agent → 编辑器：流式响应
{
  "jsonrpc": "2.0",
  "method": "agent/streamToken",
  "params": { "thread_id": "abc123", "token": "好的，" }
}
```

### Claude Code 与 Zed ACP

**当前为社区适配器支持，非原生。**

- GitHub Issue [anthropics/claude-code#6686](https://github.com/anthropics/claude-code/issues/6686) 正式请求 Claude Code 支持 ACP
- 社区项目 [szhongren/claude-code-acp](https://github.com/szhongren/claude-code-acp) 提供桥接实现
- [zed-industries/claude-code-acp](https://github.com/zed-industries/claude-code-acp) 是 Zed 官方的桥接适配器

### 其他工具支持状态

| 工具 | Zed ACP 支持状态 |
|------|----------------|
| Gemini CLI | 官方支持，Zed 官方博客有案例 |
| Cursor | 第三方服务（acpserver.org），非原生 |
| GitHub Copilot | 无官方支持 |
| Continue.dev | 通过 LangChain ACP SDK 接入 |
| LangChain | 官方 Python/JS SDK 支持 |

---

## 四、BeeAI ACP vs MCP 定位对比

| 维度 | MCP（Model Context Protocol）| BeeAI ACP |
|------|------------------------------|-----------|
| 发起方 | Anthropic | IBM / BeeAI / Linux Foundation |
| 定位 | **Model ↔ Tool/Resource** | **Agent ↔ Agent** |
| 传输 | JSON-RPC over stdio/SSE | REST HTTP |
| 核心问题 | 给 LLM 接工具、数据源 | 多 Agent 互相调用、编排 |
| 状态 | 无状态为主 | 支持有状态长任务 |
| 类比 | USB 接口（Model 接工具）| HTTP（服务间通信）|

**两者不竞争，可以叠加使用**：一个 ACP Agent 内部可以通过 MCP 调用工具。

---

## 五、在 EchoMind AgentHub 架构中的分工建议

```
用户（桌面端 IM）
    │ 消息输入
    ▼
AgentHub 后端（Python）
    ├── BeeAI ACP ──► Claude Code Agent（适配器包装）
    ├── BeeAI ACP ──► Codex Agent（适配器包装）
    ├── BeeAI ACP ──► 搜索 Agent / 分析 Agent
    │
    └── MCP ──► 工具层（文件读写、SQLite、API）
```

- **BeeAI ACP**：AgentHub 内部各 Agent 之间的编排总线，Claude Code / Codex 通过适配器接入
- **MCP**：各 Agent 访问外部工具和资源的统一接口
- **Zed ACP**：若后期需要对接编辑器（Zed/VS Code），作为编辑器端入口

---

## 六、关键结论

1. Claude Code 和 Codex CLI **目前均通过社区适配器**（非官方原生）接入这两个 ACP
2. **BeeAI ACP（REST HTTP）** 是 Agent 编排总线的最佳选择，适合第一期的多 Agent 协作架构
3. **MCP** 负责工具层，与 BeeAI ACP 分工明确，不重复
4. Zed ACP 是面向编辑器集成的协议，第一期可不优先，后期如需 IDE 集成可补充

---

## 参考资料

- [BeeAI ACP 官方文档](https://agentcommunicationprotocol.dev)
- [BeeAI GitHub: i-am-bee/acp](https://github.com/i-am-bee/acp)
- [IBM ACP 介绍](https://www.ibm.com/think/topics/agent-communication-protocol)
- [IBM ACP 实战教程](https://www.ibm.com/think/tutorials/acp-ai-agent-interoperability-building-multi-agent-workflows)
- [Zed ACP 官方页面](https://zed.dev/acp)
- [Agent Client Protocol 规范](https://github.com/zed-industries/agent-client-protocol)
- [Claude Code ACP 桥接（社区）](https://github.com/szhongren/claude-code-acp)
- [Claude Agent SDK → ACP 适配器](https://github.com/agentclientprotocol/claude-agent-acp)
- [LangChain ACP 支持](https://docs.langchain.com/oss/python/deepagents/acp)
- [Gemini CLI 接入 Zed ACP 案例](https://zed.dev/blog/bring-your-own-agent-to-zed)
- [Agent 协议综述论文](https://arxiv.org/abs/2505.02279)
