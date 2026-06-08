# 全局应用 WebSocket 设计

## 1. 目标

当前前端只在 `Messages` 页面内部按 `session_id` 建立 WebSocket 连接：

- 进入 `Messages` 页面时连接 `ws/session/{session_id}`
- 切换会话时关闭旧连接并重连新连接
- 离开 `Messages` 页面时关闭连接

这会带来两个直接问题：

- 在 `Messages` 和 `Workspace` 之间切换时，每次都要重新建立连接
- `WebSocket` 生命周期被页面绑定，无法作为整个主应用的实时事件总线复用

本次目标是把连接模型升级为：

- 用户进入主页面后，前端全局只建立一次 WebSocket 连接
- `Messages` 和 `Workspace` 共用这条连接
- 当前激活会话不再由 WebSocket URL 绑定，而是通过协议内消息切换订阅目标
- 页面切换不触发 WebSocket 重连

## 2. 背景与现状

当前结构：

- 前端 `Messages` 页面在加载完会话初始数据后，直接 `new WebSocket(createWsUrl(/ws/session/{session_id}))`
- 前端发送消息时，直接通过该连接发送纯文本消息
- 后端通过 `@router.websocket("/ws/session/{session_id}")` 接收连接
- 后端 `ConnectionManager` 以 `session_id -> [WebSocket]` 维护连接映射

这套模型的问题不是“连接不稳定”，而是“连接绑定层级太低”：

- WebSocket 被绑定在页面组件，而不是应用壳层
- WebSocket 被绑定在 URL 的 `session_id`，而不是可切换的协议上下文
- 一旦要支持跨页面复用，就必须引入真正的全局总线入口

因此本次不建议通过“把现有 `ws/session/{session_id}` 挪到更上层继续复用”来硬做。那样只会把旧模型包一层壳，不能解决会话切换和协议扩展问题。

## 3. 设计原则

本次设计遵循以下原则：

- 连接全局化：应用壳层只维护一条 WebSocket 连接
- 会话显式化：当前关注的 `session` 通过协议消息声明，不通过 URL 隐式决定
- 职责分离：连接管理、事件分发、页面状态更新拆开，不把它们继续揉进 `Messages.jsx`
- 增量改造：保留现有 REST 初始化能力和现有 runtime 事件类型，优先改变连接入口和前端消费方式
- 范围收敛：本次只解决“进入主页面后只连一次”和“会话切换不重连”，不顺手做跨会话缓存或复杂离线恢复

## 4. 范围

本次在范围内：

- 新增全局应用级 WebSocket 入口
- 前端在主页面壳层建立并持有唯一 WebSocket 连接
- `Messages` 页面改为通过全局连接订阅/切换当前会话
- `Messages` 页面改为通过结构化事件发送消息，而不是直接发送纯文本
- 全局连接在页面切换到 `Workspace` 时保持不断开
- 保留并兼容当前 runtime 推送的主要事件类型

本次不在范围内：

- 同时订阅多个会话
- 前端缓存多个会话的完整运行态快照
- 跨浏览器标签页共享同一条真实物理连接
- 复杂断线补偿、事件重放、消息序号校验
- 将 `Workspace` 页面完整改造成实时运行态面板
- 删除现有 `ws/session/{session_id}` 路由

## 5. 总体方案

### 5.1 新增全局总线连接

后端新增一个应用级 WebSocket 路由，例如：

- `GET /ws/app`（WebSocket 握手）

前端进入主页面后，在 `MainLayout` 之上或之内建立这条连接，并在整个主应用存活期间保持连接。

这条连接不绑定任何特定 `session_id`。它只代表“当前浏览器前端实例与网关之间的实时通道”。

### 5.2 用协议消息切换当前会话

当前激活会话不再体现在连接 URL 中，而是通过 WebSocket 消息显式声明。

前端在需要切换当前会话时发送：

```json
{
  "type": "session.subscribe",
  "session_id": "session-123"
}
```

后端收到后，将该连接当前关注的目标会话切换到 `session-123`，并立即向这个连接回放该会话的初始快照。

### 5.3 用结构化事件发送消息

当前前端通过 `ws.send(text)` 直接发送纯文本，这建立在“URL 已经隐含 session_id”的前提上。

改为全局总线后，发送消息必须改为结构化事件，例如：

```json
{
  "type": "chat.send",
  "session_id": "session-123",
  "content": "hello"
}
```

这样后端才能在单条全局连接上正确路由请求。

## 6. 前端设计

### 6.1 新增全局连接容器

前端新增一个应用级连接容器，推荐形态为：

- `AppSocketProvider`
- 或等价的全局 context/provider + hook

建议放置层级：

- 挂在 `MainLayout` 外层或内部，但必须覆盖 `Messages` 和 `Workspace` 两个页面

该容器职责：

- 建立 `/ws/app` 连接
- 暴露连接状态，如 `connecting/open/closed/error`
- 暴露统一的 `send(event)` 能力
- 暴露 `subscribeSession(sessionId)` 能力
- 暴露事件订阅能力，供页面消费 runtime 推送
- 在主页面存活期间负责断线重连

该容器不直接保存 `Messages` 页面专属 UI 状态，例如输入框内容、左侧列表展开状态、当前滚动位置。

### 6.2 Messages 页面职责收敛

`Messages` 页面不再自己创建或关闭 WebSocket。

改造后，`Messages` 页面只负责：

- 管理当前会话选择
- 在 `activeChat` 变化时调用 `subscribeSession(activeChat.id)`
- 继续执行该会话的 HTTP 初始数据加载
- 监听全局连接分发过来的 runtime 事件，并把事件映射到当前页面状态
- 发送消息时调用 `send({ type: 'chat.send', session_id, content })`

保留 HTTP 初始加载的原因：

- 这是当前最小改造路径
- 可以避免在第一轮就把“初始化快照获取”也完全迁移到 WebSocket 协议
- 即使 WebSocket 临时不可用，消息页仍然可以先展示静态历史和项目绑定信息

也就是说，本次优先解决“不断线”和“发送路径显式化”，而不是一次性把所有初始化逻辑都迁到 WS。

### 6.3 Workspace 页面当前策略

本次 `Workspace` 页面不强制消费全局 WebSocket 事件。

但它将天然受益于新的连接层级：

- 进入 `Workspace` 页面时不再触发 `Messages` 页的 WebSocket 关闭
- 从 `Workspace` 再切回 `Messages` 时不需要重新建立 WebSocket 物理连接

后续如果要在 `Workspace` 页显示运行态工作区树、agent 状态或计划状态，可以直接复用这条全局连接，而不用再次设计第二套连接机制。

### 6.4 事件分发边界

全局连接容器应只负责：

- 接收原始 WebSocket 事件
- 解析 JSON
- 按事件类型广播给订阅者

页面负责：

- 决定哪些事件更新哪些 UI 状态
- 忽略与当前页面无关的事件

不要把 `chatMessages`、`workspaceTree`、`planState`、`sandboxState` 等页面状态都上提到 provider。那会把这次“连接架构优化”演变成一次大范围前端状态重构。

## 7. 后端设计

### 7.1 新增应用级 WebSocket 路由

新增：

- `@router.websocket("/ws/app")`

该路由用于：

- 接受全局应用连接
- 接收结构化指令事件
- 根据连接当前订阅的 `session_id` 推送对应 runtime 事件

### 7.2 连接管理模型升级

当前 `ConnectionManager` 只有一层映射：

- `session_id -> [WebSocket]`

这适用于 session 级 URL 连接，但不适用于全局总线连接。

本次应升级为能表达以下信息的模型：

- 某条连接当前订阅的是哪个 `session_id`
- 某个 `session_id` 当前有哪些连接在订阅

推荐目标能力，而不是强绑定某一种内部数据结构：

- `connect_app(ws)`
- `disconnect_app(ws)`
- `subscribe(ws, session_id)`
- `unsubscribe(ws)`
- `broadcast(session_id, event)`

这样可以同时支持：

- runtime 仍然按 `session_id` 广播事件
- manager 再把事件转发给当前订阅该会话的全局连接

### 7.3 初始快照发送

当客户端发送 `session.subscribe` 后，后端需要立即向该连接推送当前会话的快照。

优先复用现有能力：

- `_send_chat_snapshot(session_id, ws)`
- `_send_workspace_snapshot(session_id, ws)`

这样本轮不需要重新发明快照装配逻辑。

预期会推送的事件包括：

- `message.history.sync`
- `workspace.snapshot`
- `workspace.tree.snapshot`
- `plan.snapshot`
- `sandbox.snapshot`
- `agent.snapshot`

### 7.4 发送消息入口

当后端收到以下事件：

```json
{
  "type": "chat.send",
  "session_id": "session-123",
  "content": "hello"
}
```

应执行与当前 `/ws/session/{session_id}` 相同的消息分发链路：

- 记录用户消息
- 调用 agent service 触发运行
- 让 runtime 后续继续通过 `manager.broadcast(session_id, event)` 推送状态

### 7.5 兼容策略

本次不删除现有：

- `/ws/session/{session_id}`

原因：

- 可以降低回归风险
- 便于分阶段迁移和调试
- 旧测试与旧调用方可以暂时保留

等前端完全切换到 `/ws/app` 且验证稳定后，再决定是否废弃旧路由。

## 8. 协议设计

### 8.1 客户端到服务端事件

#### `session.subscribe`

作用：切换当前连接关注的会话。

示例：

```json
{
  "type": "session.subscribe",
  "session_id": "session-123"
}
```

要求：

- `session_id` 必填
- 如果会话不存在，服务端返回错误事件
- 重复订阅同一会话应是幂等的

#### `chat.send`

作用：向指定会话发送用户消息。

示例：

```json
{
  "type": "chat.send",
  "session_id": "session-123",
  "content": "hello"
}
```

要求：

- `session_id` 必填
- `content` 必须是非空字符串
- 服务端必须校验参数，不允许空消息直接进入 agent 调度链路

### 8.2 服务端到客户端事件

保留现有 runtime 事件类型，不要求本轮统一重命名。包括但不限于：

- `message.history.sync`
- `chat.status`
- `task.status`
- `agent.token`
- `agent.done`
- `workspace.snapshot`
- `workspace.tree.snapshot`
- `workspace.tree.updated`
- `plan.snapshot`
- `plan.updated`
- `sandbox.snapshot`
- `sandbox.status`
- `agent.snapshot`
- `agent.status`
- `error`

可新增一个轻量握手事件，例如：

- `app.ready`

它不是必须项，但有助于前端区分“已建立 TCP/WS 连接”和“应用协议可用”。

## 9. 页面行为细节

### 9.1 进入主页面

- 建立全局 `/ws/app` 连接
- 如果连接失败，主页面保留可见但降级为 HTTP 能力
- 前端显示轻量连接错误状态，但不阻塞页面基础浏览

### 9.2 进入 Messages 页面

- 加载 session 列表
- 确定 `activeChat`
- 继续用 HTTP 拉取消息历史、session 信息、project 信息
- 对当前 `activeChat.id` 发送 `session.subscribe`

### 9.3 切换会话

- 不关闭全局连接
- HTTP 继续拉取目标会话初始数据
- 发送新的 `session.subscribe`
- 清空当前消息流式拼接态，例如当前 streaming message id

### 9.4 切到 Workspace 页面

- 不关闭全局连接
- 不强制取消当前订阅

本轮建议保持“最后一次订阅的会话仍然有效”。原因是：

- 这样用户从 `Workspace` 返回 `Messages` 时不会因为连接上下文被重置而增加恢复成本
- 这也是最小实现

### 9.5 发送消息

- 如果全局连接未打开，则不允许直接发送 WS 消息
- 前端给出明确错误提示，例如“实时连接未建立，暂时无法发送消息”
- 本轮不额外引入 HTTP 发送兜底

## 10. 错误处理

### 10.1 前端

- 连接失败：保留页面可浏览，显示实时更新暂停提示
- 订阅失败：清空当前 streaming 状态，显示当前会话无法订阅
- 发送失败：提示消息发送失败，不伪造成功态
- 服务端返回 `error` 事件：根据当前页面分别映射到 `chatError` / `workspaceError`

### 10.2 后端

- 非法 JSON：返回 `error`
- 缺少 `type`：返回 `error`
- 不支持的事件类型：返回 `error`
- 缺少 `session_id`：返回 `error`
- `session_id` 不存在：返回 `error`
- `chat.send.content` 为空：返回 `error`

错误处理原则：

- 不因为单次协议错误直接让整个连接崩掉
- 优先返回结构化错误事件给前端

## 11. 测试策略

### 11.1 后端

新增或调整 WebSocket 测试，至少覆盖：

- 连接 `/ws/app` 成功
- 发送 `session.subscribe` 后收到快照事件
- 发送 `chat.send` 后触发原有 agent 调度链路
- 非法事件返回 `error`
- 一个连接切换订阅到另一个会话后，只接收新会话事件
- `manager.broadcast(session_id, event)` 仍能把事件发给订阅该会话的连接

### 11.2 前端

新增或调整前端测试，至少覆盖：

- `MainLayout` 或 provider 层只建立一次 WebSocket
- 页面从 `Messages` 切到 `Workspace` 再切回时，不重新创建物理连接
- `Messages` 切换 `activeChat` 时发送 `session.subscribe`
- 发送消息时使用 `chat.send` 结构化事件
- 连接关闭或错误时，消息输入正确进入不可发送状态

## 12. 实施边界与迁移顺序

建议迁移顺序：

1. 先新增后端 `/ws/app` 与新的 manager 能力
2. 保持旧 `/ws/session/{session_id}` 不动，确保兼容
3. 新增前端 `AppSocketProvider`
4. 让 `Messages` 页面切换为消费 provider
5. 验证跨页面切换不重连
6. 后续再评估是否让 `Workspace` 页面订阅运行态事件

这样可以避免一次性同时改动：

- 后端协议
- 前端连接层
- 前端所有页面状态来源

## 13. 关键决策

- 采用真正的全局总线连接，而不是把现有 session 路由提升到更高层硬复用
- 本轮保留 HTTP 初始数据加载，WebSocket 负责实时性与会话订阅切换
- 本轮不做多会话并发订阅
- 本轮不把页面业务状态整体上提到全局 store
- 本轮保留旧 `/ws/session/{session_id}` 路由以降低回归风险

## 14. 成功标准

以下结果同时满足，视为本次设计落地成功：

- 用户进入主页面后，前端只建立一次 WebSocket 连接
- 在 `Messages` 和 `Workspace` 间切换时，不因页面卸载而重连 WebSocket
- 切换不同会话时，只发送订阅切换事件，不销毁并重建物理连接
- `Messages` 页面仍能正常接收 token、状态、workspace/runtime 事件
- 发送消息路径改为结构化协议事件且功能不退化
