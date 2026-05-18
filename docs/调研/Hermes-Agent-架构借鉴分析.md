# Hermes Agent 架构借鉴分析（源码核对版）

## 调研目标

本报告基于 Hermes Agent 本地源码目录 `docs/调研/hermes-agent-src/` 的实际代码，对其运行时架构、模块边界、session / memory / profile / tools / compression / gateway / cron / delegation 等关键设计做一次源码级确认，并与 EchoMind 当前一期架构方案进行对比，提炼出可直接借鉴的设计原则。

本次调研同时参考 EchoMind 现有架构文档：

- `docs/第一期/00-整体架构草案.md`
- `docs/第一期/02-后端最小落地架构.md`
- `docs/第一期/05-Session模块详细方案.md`

本报告重点回答以下问题：

1. Hermes 的主运行时骨架到底是什么
2. Hermes 的 session、memory、profile、tool、compression、gateway、cron 分别由谁控制
3. Hermes 的异步线程和后台任务到底在做什么，不在做什么
4. Hermes 的哪些思想适合 EchoMind 一期借鉴，哪些不应直接照搬
5. EchoMind 当前 `chat + agent + tools + session + memory + profile` 架构，应如何吸收 Hermes 的源码级经验

## 总结结论

Hermes 最值得 EchoMind 借鉴的，不是它作为本地 CLI / gateway 产品的具体落地方式，而是以下几条已经被源码验证的架构原则：

- 用一个同步、可中断的单 agent loop 作为主生成链路核心
- 把 session persistence 作为主链路骨架，而不是把状态寄托在临时内存 history
- 明确区分稳定 system prompt 前缀和 API-call-time 临时注入层
- 把 memory / profile / session search / compression / cron / delegation 都视为主循环外围能力，而不是让它们主导主循环
- 把工具系统做成独立 registry + discovery + availability checking + dispatch 边界
- 把“每 turn 的轻量 recall / sync”和“session 级 / 后台级的重型维护”分开

Hermes 不适合 EchoMind 直接照搬的部分也很明确：

- 它是本地代理产品，不是多用户服务端业务后端
- 它的 built-in memory 真源是 `MEMORY.md / USER.md`，而不是结构化数据库
- 它的 session lineage 主要服务 context compression split，不适合 EchoMind 当前“单 session + assistant 回复组候选集”模型
- 它的 plugins / skills / hub / kanban / gateway 生态很强，但对 EchoMind 一期来说过重

因此，EchoMind 的正确借鉴方向是：

- 借鉴 Hermes 的运行时分层与职责收口
- 不照搬 Hermes 的文件型存储真源
- 保留 EchoMind 自己的 PostgreSQL 真源与模块 owner 设计
- 把 Hermes 的 memory/search/compression/background 经验翻译成 EchoMind 的模块化服务边界

## 一、调研范围与源码依据

本次调研重点核对的源码路径包括：

- `run_agent.py`
- `agent/conversation_loop.py`
- `agent/prompt_builder.py`
- `agent/context_compressor.py`
- `agent/memory_manager.py`
- `hermes_state.py`
- `model_tools.py`
- `tools/registry.py`
- `tools/memory_tool.py`
- `tools/delegate_tool.py`
- `tools/interrupt.py`
- `gateway/run.py`
- `gateway/session.py`
- `cron/scheduler.py`
- `plugins/memory/honcho/__init__.py`
- `plugins/memory/honcho/session.py`

其中，最关键的源码事实包括：

- 主循环真实入口是 `agent/conversation_loop.py::run_conversation()`，`run_agent.py` 只是承载 `AIAgent` 容器与辅助方法
- system prompt 采用 session 级缓存，只有新 session 或 compression 后才重建
- memory provider 在每 turn 开头显式接收 `on_turn_start(...)` 信号，再进行 `prefetch_all(...)`
- turn 结束后，外部 memory provider 会收到 `sync_all(...)` 与 `queue_prefetch_all(...)`
- `on_session_end` hook 在每次 `run_conversation()` 结束时触发，但不等于整个长会话真正结束
- built-in memory 使用冻结快照模式：中途写盘，但不重建当前 session prompt
- Honcho 这类外部 memory provider 既有 turn 前 recall，也有 turn 后 sync，还有独立后台 flush / prefetch 线程
- `delegate_task` 是同步子代理编排，不是 durable background worker system

## 二、EchoMind 当前架构基线

在对比 Hermes 之前，需要先确认 EchoMind 当前的一期架构基线。

根据 `docs/第一期/02-后端最小落地架构.md`，EchoMind 当前已经明确采用：

- 模块化单体
- 按业务能力分模块，而不是按横向技术层切目录
- 以 `chat / user / agent / memory / profile / session / models / tools / shared / platform` 为主模块划分

其中关键 owner 边界已经相当清晰：

- `chat`：HTTP / SSE 接入、流式输出、stop / retry / regenerate、run 生命周期控制
- `agent`：主链路 orchestration、prompt assembly、runtime
- `memory`：长期记忆真源与同步
- `profile`：用户画像真源与同步
- `session`：会话消息、assistant 回复组、摘要真源
- `tools`：工具注册、分发、执行、审计

根据 `docs/第一期/05-Session模块详细方案.md`，EchoMind 已经正式确认：

- `session` 是 `sessions / messages / session_summaries` 的 owner
- 不采用 Hermes 那种“compression split 后 session lineage 作为主模型”的方案
- 一期采用“单 session + assistant 回复组候选集”的模型
- `chat / agent / recall / compression` 不允许直接跨模块写 session 相关表

这意味着 EchoMind 与 Hermes 的真正比较，不是“数据库表结构像不像”，而是：

- 谁掌控主循环
- 谁掌控 prompt 稳定层
- 谁拥有 session 真源
- recall / compression / background 是否处于正确的外围层级

## 三、Hermes 的整体架构图景

从源码看，Hermes 的整体运行时可以概括为：

- 入口层：CLI、gateway、TUI gateway、batch runner、ACP adapter、cron
- 主执行层：`AIAgent`
- 主循环层：`agent/conversation_loop.py`
- prompt 层：`agent/prompt_builder.py`
- memory 层：`tools/memory_tool.py` + `agent/memory_manager.py` + 外部 memory plugins
- session storage 层：`hermes_state.py`
- tools 层：`model_tools.py` + `tools/registry.py` + `tools/*.py`
- gateway / platform runtime：`gateway/run.py` + `gateway/session.py`
- 后台增强层：cron、process watcher、subagent orchestration、memory provider background sync

最重要的判断是：

- Hermes 的主体不是“多个长期运行 agent 的自治协作系统”
- Hermes 的主体是“一个同步主循环 + 多个外围增强层”

这与 EchoMind 一期的理想方向高度一致。

## 四、Hermes 的主循环与运行时分层

### 1. 核心对象是 `AIAgent`

`run_agent.py` 中的 `AIAgent` 承载了运行时状态，但真正的 turn loop 已经抽到 `agent/conversation_loop.py::run_conversation()`。

从源码看，`AIAgent` 负责的主要是：

- 持有 session / model / provider / callbacks / memory manager / tool schema 等状态
- 作为主循环中的 runtime 容器
- 暴露 `interrupt()`、`clear_interrupt()`、`_sync_external_memory_for_turn()`、`_compress_context()` 等关键方法

### 2. 一次 turn 的真实处理流程

`agent/conversation_loop.py` 里，一次 turn 的真实生命周期大致是：

1. 建立本次运行的线程上下文、日志上下文、interrupt 上下文
2. 追加 user message 到 `messages`
3. 决定是否复用已有 `_cached_system_prompt`
4. 如果是新 session，则构建 system prompt，并触发 `on_session_start`
5. 在 turn 开头调用 memory manager 的 `on_turn_start(...)`
6. 执行 `prefetch_all(...)`，把 recall 结果缓存到本 turn
7. 必要时做 preflight compression
8. 构造 API messages，并把 recall 结果作为临时注入层回注
9. 调用模型
10. 若返回 tool calls，则执行工具并将结果追加回 history
11. 若返回最终 assistant 文本，则形成最终结果
12. turn 结束后执行外部 memory sync、后台 review、`on_session_end`

这说明 Hermes 的主循环本质上就是：

- 同步 loop
- 中间允许多次 tool roundtrip
- turn 结束后做后处理

### 3. 中断是 runtime 的一等能力

Hermes 很强调 turn 的可中断性。

`tools/interrupt.py` 不是一个简单全局 flag，而是：

- 以线程 ID 为作用域的中断集合
- 一个 session 的 interrupt 不会误杀另一个 session 所在线程的工具执行

而在 `conversation_loop.py` 中：

- 进入 turn 时先记录 `_execution_thread_id`
- 在 loop 内每轮显式检查 `_interrupt_requested`
- 一旦中断，当前 turn 立即 break 出去

这对 EchoMind 的启发非常明确：

- `stop` 不应只是 API 层状态字段
- 它必须成为 agent runtime 的一等控制信号
- 模型流、工具执行、子代理执行都要能感知并在安全点停止

## 五、Prompt Assembly：稳定前缀与动态层

### 1. `active_system_prompt` 是 session 级缓存

在 `conversation_loop.py:315-354`，Hermes 明确实现了 system prompt 缓存逻辑：

- 如果 `_cached_system_prompt` 已存在，则直接复用
- 如果当前是 continuation session，优先从 `SessionDB` 里取之前存下来的 `system_prompt`
- 只有真正的新 session 才重新 `agent._build_system_prompt(...)`

这里的核心思想不是“省一次字符串拼接”，而是：

- 保护 prompt cache
- 保护 memory snapshot 稳定性
- 避免 session 中途 memory 改了就重写 system prompt

### 2. 稳定层的组成

从 `agent/prompt_builder.py` 和 `AIAgent._build_system_prompt()` 的调用关系看，稳定层通常包括：

- agent identity
- memory guidance / session search guidance / skills guidance / tool-use guidance
- 平台提示
- skills index
- context files（如 `AGENTS.md`、`SOUL.md`、`.hermes.md`）
- built-in memory snapshot
- 外部 memory provider 的 system prompt block
- gateway session context prompt

### 3. 动态层的组成

在 `conversation_loop.py:680-689` 可以看到，turn 前 prefetch 的 external memory context 并不会改写原始 `messages`，而是：

- 在 API-call-time 注入到当前 user message 周围
- 作为 ephemeral context 使用
- 不落入持久 transcript

因此 Hermes 的 prompt 输入层源码上可以明确拆成两部分：

稳定层：

- `_cached_system_prompt`
- 内建 memory snapshot
- gateway session context
- skills / platform / context files

动态层：

- 当前 user message
- 本 turn 的 memory recall
- 本 turn 的 steer / runtime 注入
- 当前 tool result
- compression summary

### 4. 对 EchoMind 的启发

EchoMind 的 `Prompt Assembler` 设计应继续坚持当前文档中的思路：

- 稳定层：system identity、memory snapshot、profile snapshot、tool guidance、project context
- 动态层：当前 user message、recall summary、compression summary、tool results、runtime flags

最重要的是：

- 数据库真源不等于 prompt 实时刷新
- 本次 run 的 memory / profile 快照应保持稳定
- run 中后台 job 更新了数据库，也不要强制重写当前 run 的 system prompt

## 六、Session Storage 与 Session 上下文控制

### 1. Hermes 的 session persistence 骨架

`hermes_state.py` 实现了 Hermes 的会话真源：

- SQLite
- WAL 模式优先
- `sessions`
- `messages`
- `messages_fts`
- trigram FTS

表结构保持得比较轻：

- `sessions`：元数据、system_prompt、tokens、cost、parent_session_id 等
- `messages`：`role / content / tool_call_id / tool_calls / tool_name / timestamp / reasoning`

它刻意把复杂语义留在应用层，而不是在 DDL 里建很重的消息树模型。

### 2. Hermes 的 `parent_session_id` 是做什么的

从 `hermes_state.py` 和 compression 相关代码可知：

- `parent_session_id` 主要服务 compression split 和 lineage
- 不是为了像 EchoMind 一期那样承接 regenerate 多候选回复组

因此：

- Hermes 的 lineage 设计不适合直接翻译成 EchoMind 的回复组模型

### 3. 什么是 gateway session context prompt

`gateway/session.py` 实现了一套很明确的 session context 注入机制：

- `SessionSource` 描述消息来自哪里
- `SessionContext` 描述平台、用户、会话、home channel 等上下文
- `build_session_context_prompt(...)` 将这些运行态信息组装成一段提示词，注入 system prompt

它告诉模型的不是“如何回答用户”，而是：

- 当前来源平台是什么
- 当前对话是私聊、群组还是 thread
- 当前是否是多用户共享 session
- 当前连接了哪些平台
- 是否有 home channel
- 某些平台是否具备专属 API 能力

这是一个非常值得 EchoMind 借鉴的设计点：

- session 不只是消息存储
- session 还可以向 agent 提供“当前对话处境”的运行时上下文

### 4. 对 EchoMind 的启发

EchoMind 的 `session` 模块可以继续保持当前 owner 边界，同时引入一层更明确的“会话上下文视图”：

- 当前用户身份最小上下文
- 当前 session 元信息
- 当前会话来源和 channel/thread 语义
- 是否多用户共享
- 交付/通知/外部通道能力

这部分可以作为 `agent` 构建稳定 prompt 前缀时的一个输入块，但 owner 仍然是 `session`。

## 七、Memory 与 Profile：源码级真实分层

### 1. built-in memory 的真实控制方式

`tools/memory_tool.py` 明确实现了 Hermes 的 built-in memory：

- `MEMORY.md`
- `USER.md`

其核心机制是 `MemoryStore` 的双态结构：

- `memory_entries / user_entries`：live state，可被本 session 的 tool call 修改
- `_system_prompt_snapshot`：在 `load_from_disk()` 时冻结，用于 system prompt 注入

这意味着：

- memory tool 写入会立即落盘
- 但当前 session 的 system prompt 不会被重写
- 新快照通常只在下一次 session start 时生效

### 2. `USER.md` 就是 Hermes 的内建 profile

Hermes 并没有一个和 EchoMind 完全对等的结构化 profile service。

在 built-in memory 层：

- `MEMORY.md` 更偏 agent 的长期笔记
- `USER.md` 更偏用户画像、偏好、沟通风格、稳定习惯

所以从源码上看，Hermes 的内建“profile”本质上就是：

- `USER.md` 这一份冻结快照

### 3. 外部 memory provider 的真实控制方式

`agent/memory_manager.py` 是 Hermes 对外部记忆系统的统一接入点。

它负责：

- `build_system_prompt()`：汇总 provider 的稳定提示块
- `prefetch_all()`：turn 前 recall
- `queue_prefetch_all()`：下一轮预热
- `sync_all()`：turn 后同步
- `on_turn_start()`：向 provider 发出 turn 节拍信号

这说明 Hermes 非常明确地区分了：

- built-in stable memory snapshot
- external provider recall / sync lifecycle

### 4. Honcho 在 Hermes 中到底是什么

根据 `plugins/memory/honcho/__init__.py` 和文档：

- Honcho 是 Hermes 的外部 memory provider 之一
- 它提供 cross-session user modeling、peer card、semantic search、session context、dialectic reasoning、persistent conclusions

可以把它理解成：

- 一个外部长期记忆与画像服务
- Hermes 把对话同步给它，它再向 Hermes 提供 recall / profile / reasoning 能力

### 5. `on_turn_start()` 和 `prefetch_all()` 真实在做什么

源码里，`conversation_loop.py` 在每个 turn 开头先执行：

- `memory_manager.on_turn_start(turn_number, message)`
- 然后再执行 `prefetch_all(query)`

以 Honcho 为例：

- `on_turn_start()` 主要更新 `_turn_count`
- 后续是否允许执行 context refresh / dialectic refresh，由 `contextCadence` / `dialecticCadence` 决定

因此：

- `on_turn_start()` 是 provider 的节拍信号
- `prefetch_all()` 才是本 turn 真的去拿 recall context 的动作

### 6. turn 后的 `sync_all()` 与 `queue_prefetch_all()` 在做什么

`run_agent.py::_sync_external_memory_for_turn()` 在 turn 结束后调用：

- `sync_all(original_user_message, final_response)`
- `queue_prefetch_all(original_user_message)`

它们的语义分别是：

- `sync_all`：把本轮用户消息和最终 assistant 回复同步给外部 provider
- `queue_prefetch_all`：为下一轮预热 context / recall

这里的一个重要细节是：

- interrupted turn 不会进入这一步
- Hermes 明确避免把用户未真正看到完成结果的半成品 turn 写进外部记忆

### 7. 对 EchoMind 的启发

EchoMind 当前文档已经把 `memory` 和 `profile` 拆成两个模块，这比 Hermes 更适合服务端后端。

建议继续坚持：

- `memory`：长期高价值结构化事实、偏好、约束
- `profile`：关于用户是谁、怎么交流、稳定偏好的高层画像
- `session search`：历史消息与历史摘要检索能力
- `session_summaries`：compression / recall 的中间真源

同时借鉴 Hermes 的运行时控制节奏：

- turn 前 recall
- turn 后 sync
- session 结束或后台 job 做更重的 extraction / conclude / rebuild

## 八、Tools：Registry + Discovery + Dispatch 的边界

### 1. 工具注册方式

`tools/registry.py` 定义了 Hermes 的工具注册中心。

机制很清楚：

- 每个 `tools/*.py` 在模块加载时调用 `registry.register(...)`
- `model_tools.py` 通过 `discover_builtin_tools()` 扫描并导入工具模块
- registry 管理 schema、handler、toolset、availability check、dynamic schema override

### 2. `model_tools.py` 的角色

`model_tools.py` 不是工具实现层，而是：

- 工具发现与 schema 暴露层
- toolset 过滤层
- sync/async bridge 层
- `handle_function_call(...)` 的公开入口层

这说明 Hermes 明确区分了：

- tool implementation
- tool registry
- tool exposure/filtering
- tool dispatch orchestration

### 3. 对 EchoMind 的启发

EchoMind 当前文档中的 `tools/service.py + registry.py + dispatcher.py + audit.py` 设计是对的，应继续坚持。

尤其应借鉴 Hermes 的几点：

- 工具发现和注册不要散落在 agent loop 里
- availability check 要成为 registry 的正式能力
- tool schema 允许少量 runtime override
- toolset / capability filtering 应该统一发生在工具边界层，而不是主循环到处 if/else

## 九、Compression：在线主压缩，而不是展示摘要

### 1. Hermes 的 compression 是主运行时能力

`agent/context_compressor.py` 不是简单的“聊天摘要器”，而是：

- 一套运行时 context compaction 机制
- 通过辅助模型对中段消息做结构化摘要
- 保留 head / tail
- 先做旧 tool output prune

它强调的几个点非常明确：

- summary 是 reference only，不是当前任务指令
- summary 结构化，且可迭代更新
- image / tool result /多模态内容都要纳入 token 预算考虑

### 2. Hermes 的 session split 语义

Hermes 的 compression 与 `parent_session_id` 结合后，会出现 continuation session / lineage 语义。

这对 Hermes 本地产品是合理的，因为它需要：

- 在 SQLite 历史中保留压缩前后脉络
- 让用户还能检索 lineage

但对 EchoMind 一期来说：

- 没必要照搬成 session split 主模型
- 更适合保留在 `session_summaries` 中表达 compression / recall 结果

### 3. 对 EchoMind 的启发

EchoMind 应借鉴的是：

- 压缩是主链路 runtime 正式能力
- 摘要不是给前端展示用的一句话概述
- 摘要应该承担 recall / compression 的中间真源角色

最适合 EchoMind 当前边界的落地方向是：

- `CompressionService` 负责是否压缩、如何压缩、生成什么结构化摘要
- `RecallService` 负责 session history / summaries 的检索和归纳
- `SessionService` 负责真正写 `session_summaries`

## 十、Gateway、TUI、Cron 与后台增强层

### 1. Gateway 做的是什么

`gateway/run.py` 说明，gateway 是一个长生命周期 runtime，而不是简单 webhook handler。

它主要负责：

- 管理平台接入
- 管理 per-session agent cache
- 处理 slash command / stop / resume / auto-continue
- 管理消息重放与 transcript replay
- 管理 session expiry
- 驱动 cron / background process 通知 / adapter 生命周期

也就是说，Hermes 的很多“异步后台”能力，不在主 agent loop 里，而在 gateway 这一层。

### 2. TUI gateway 做的是什么

`tui_gateway/server.py` 不是第二套 agent runtime，而是：

- 把前端 TUI 输入转成 agent turn
- 把流式输出和工具事件推回 UI
- 跟踪 background process completion queue
- 当后台进程完成时，自动生成一条新的 agent turn 通知

这说明 TUI 的后台线程主要是在做：

- UI/IO 协调
- 进程完成通知
- 状态事件转发

而不是替代主 agent 做推理。

### 3. Cron 做的是什么

`cron/scheduler.py` 明确写了：

- gateway 每 60 秒在后台线程里 tick 一次 cron scheduler
- cron tick 用文件锁防止重复执行
- cron job 会解析 due jobs、构造 prompt、选择 toolset、执行作业、投递结果

这再次证明 Hermes 的后台增强层是：

- 定时调度
- housekeeping
- 进程通知
- 后台 delivery

而不是“持续陪跑的 review agent 线程”。

### 4. Hermes 的后台线程到底做什么

源码确认下来，Hermes 的后台线程主要分几类：

- IO 与事件转发线程：TUI stdout/stderr drain、event publisher、notification poller
- memory provider 线程：Honcho async writer、prefetch thread、sync thread
- delegation 线程池：`delegate_task` batch mode 的 `ThreadPoolExecutor`
- process watcher / cleanup 线程：terminal background process registry、cleanup worker
- cron tick 线程：gateway 驱动的定时调度

这些线程主要做的是：

- 不阻塞主回复链路的 IO / 同步 / 预热 / 清理 / 并行子任务

它们没有在做的是：

- 一个独立持续推理的长期后台主 agent
- 每句话都自动跑一次重型 review

### 5. 对 EchoMind 的启发

EchoMind 的后台增强层可以更明确地设计为：

- post-run async jobs
- periodic jobs
- dead-letter retry / provider sync retry

适合 run 后异步触发的作业：

- memory extract
- profile refresh
- session summary refresh
- provider sync

适合周期调度的作业：

- provider retry
- stale session cleanup
- 长会话 summary rebuild
- 画像/记忆质量治理

## 十一、Delegation：同步子代理编排，不是 durable worker

### 1. `delegate_task` 的真实语义

`tools/delegate_tool.py` 非常明确：

- child agent 有 fresh context
- child 有独立 task_id 和受限 toolset
- parent 只拿到 child summary
- parent 阻塞等待 child 完成

### 2. batch delegation 的并行方式

batch 模式使用 `ThreadPoolExecutor` 并发跑多个 child。

但它做了非常多控制：

- 并发上限
- depth 限制
- role 区分（leaf / orchestrator）
- parent interrupt 时对子代理传播停止信号
- 子代理状态跟踪与 hook 回调
- cost rollup

### 3. 这说明什么

Hermes 的 orchestration 更准确的定义是：

- 同步子代理编排
- 短生命周期 reasoning worker fanout

而不是：

- durable background worker system

### 4. 对 EchoMind 的启发

EchoMind 可以把这项能力放到二期，而不是一期主链路依赖。

如果将来借鉴，建议从最小版本开始：

- 只允许 research / code review / large analysis 这类任务触发 subagent
- child 使用 fresh context + restricted tools
- child 只回传 final summary
- child 的所有中间状态仍通过当前 run / session 边界统一管理

## 十二、Hermes 与 EchoMind 的关键对比

### 1. 相同点

- 都适合采用同步单 agent loop 作为主链路
- 都需要明确 tool dispatch boundary
- 都需要 session persistence / recall / compression
- 都需要把 memory 与 history search 分层
- 都适合把 background enhancement 从主回复链路里剥离出去

### 2. 不同点

- Hermes 是本地 / gateway 型 agent 产品，EchoMind 是多用户服务端后端
- Hermes 的 built-in memory 是文件型真源，EchoMind 应坚持 PostgreSQL 真源
- Hermes 的 session lineage 服务 compression split，EchoMind 当前主模型是单 session + assistant 回复组候选集
- Hermes 有很强的 plugin / skills / kanban / cron 产品能力，EchoMind 一期不应背上全部复杂度

### 3. EchoMind 已经比 Hermes 更适合服务端的地方

从现有文档看，EchoMind 已经做对了几件事：

- 明确 `session` 是 owner 模块
- 明确 `chat` 不直接写 session 表
- 明确 `memory` 与 `profile` 分模块真源
- 明确 stop / retry / regenerate 是 chat runtime 控制语义
- 明确 `tools` 应独立成 registry + dispatcher + audit 边界

真正要借鉴 Hermes 的，不是推翻这些，而是进一步把 runtime 协作关系收紧。

## 十三、对 EchoMind 的具体借鉴建议

### 1. 主链路

建议继续坚持：

- `chat` 负责 HTTP / SSE、run lifecycle、stop / retry / regenerate
- `agent` 负责同步主循环 orchestration
- `tools` 负责 registry + dispatch + execution + audit
- `session` 负责消息与摘要真源

最推荐的协作关系是：

1. `chat` 收请求，创建 / 读取 run state
2. `session` 追加 user message
3. `agent` 加载 session history、memory snapshot、profile snapshot
4. `agent` 组装稳定 prompt 前缀与动态 recall 层
5. `agent` 调模型
6. 若有 tool calls，则调 `tools`
7. `tools` 结果回写 `session`
8. `agent` 继续 loop，直到产出最终 assistant
9. `session` 落库最终 assistant / tool 消息 / summaries
10. 主链路结束后投递 async jobs

### 2. Prompt 层

建议正式拆成：

稳定层：

- system identity
- user identity snapshot
- memory snapshot
- profile snapshot
- tool guidance / schema hint
- static project / tenant context
- session context block

动态层：

- 当前 user message
- recall summary
- compression summary
- 当前 tool result
- runtime cancel / budget / warning 信号

### 3. Session 模块

建议继续坚持当前 `SessionService` owner 方案，同时补一层：

- 面向 agent 的 `SessionContextView`
- 面向 recall/compression 的 `SessionSummaryAccess`

这样既保持存储真源边界，也让 session 成为 prompt 稳定上下文的正式输入者。

### 4. Memory / Profile 模块

建议把 Hermes 的 frozen snapshot 思路翻译为：

- 数据库是真源
- 每次 run 开始时加载 memory/profile snapshot
- snapshot 在本次 run 内保持稳定
- run 中后台 job 可以更新数据库，但不强制改写当前 run prompt

### 5. Recall / Compression

建议明确分层：

- `RecallService`：历史摘要与历史消息召回
- `CompressionService`：运行时压缩与结构化摘要生成
- `SessionService`：负责摘要落库

### 6. 后台增强层

建议正式抽象为异步作业层，而不是模糊的“review 线程”：

- memory extract job
- profile refresh job
- session summary rebuild job
- provider sync job
- retry / dead-letter job

### 7. 二期可选能力

如果 EchoMind 将来需要向 Hermes 靠拢，可以在二期考虑：

- subagent delegation
- richer external memory provider cadence
- cron / scheduled agent run
- background process notification surface

但这些都不应成为一期的前置依赖。

## 十四、最终结论

Hermes 最值得 EchoMind 借鉴的，是一种非常清晰的运行时哲学：

- 用同步主循环承接生成任务
- 用工具调用扩展能力边界
- 用 session persistence 承接可恢复上下文
- 用 frozen snapshot 保护 prompt 稳定前缀
- 用 memory / profile / recall / compression / background maintenance 作为增强层，而不是主导层

对 EchoMind 来说，最合理的路径不是“做成 Hermes 的服务端版”，而是：

- 保留自己已经建立起来的 PostgreSQL 真源与模块 owner 边界
- 在运行时层面吸收 Hermes 的单主循环、稳定前缀、tool dispatch、memory/search 分层思想
- 把异步增强正式收敛成后台作业层
- 把复杂度集中在 `agent orchestrator` 与各模块公开 service 的协作关系上

如果以当前一期文档为基线，EchoMind 已经在模块边界上走在正确方向上；接下来真正需要向 Hermes 学习的，是如何把这些边界转化成一个更干净、更可中断、更可压缩、更可扩展的 runtime 骨架。
