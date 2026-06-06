# Hermes Agent 设计总结（分享版）

## 1. 项目核心思路

Hermes Agent 的核心不是一个“很多 agent 并行自治”的系统，而是一个以 **单次 turn 主循环** 为中心的运行时。

源码/文档明确事实：

- 每次用户发来一条消息，系统都会启动一轮完整的处理流程
- 这轮流程内部会依次做：整理消息历史、准备稳定提示词、补充本轮可能相关的记忆、调用模型、执行工具、保存结果

来源：`agent/conversation_loop.py`，`website/docs/developer-guide/agent-loop.md`

基于实现的工程解释：

- 记忆、会话检索、压缩、提示词缓存、子代理、定时任务、后台长任务监控，都只是围绕这轮主流程服务的外围能力
- 先把主循环做稳定
- 再把 recall / compression / background / delegation 接到主循环边上

## 2. 主 Agent 循环与异步任务编排

Hermes 的主循环是标准的 turn-based agent loop，但实现上比常见聊天壳更完整。

源码/文档明确事实：

一次对话回合的关键顺序大致是：

- 先把已有历史复制出来，避免直接改原始数据
- 追加本轮用户消息
- 复用已有的稳定提示词，或者在新会话时重新构建
- 给记忆系统一个“新回合开始”的信号，并准备本轮可能相关的 recall 内容
- 按当前模型接口格式整理请求消息
- 调用模型
- 如果模型请求调用工具，就执行工具并把结果接回消息流，再继续推理
- 如果模型给出最终回复，就保存会话结果，并把这轮信息同步到长期记忆系统

来源：`agent/conversation_loop.py`，`website/docs/developer-guide/agent-loop.md`

源码/文档明确事实：

- 子代理调用不是独立后台任务，而是父 agent 发起一个子任务后等待结果回来，再继续自己当前这轮流程
- 多个工具调用可以并发执行，但这属于**当前这一轮内部的加速机制**

来源：`tools/delegate_tool.py`，`website/docs/developer-guide/agent-loop.md`，`AGENTS.md`

基于实现的工程解释：

- 真正偏后台的能力主要有三类：定时触发的新任务、长时间运行命令的状态跟踪、以及长期记忆系统的异步写入和预热
- 这些并发能力并不构成一个长期运行的统一任务调度系统
- 主循环本身尽量保持清晰和可中断
- 真正需要慢慢跑、定时跑、后台跟踪的事情，放到主循环之外处理

## 3. Memory 与 User Profile 的修改方式

Hermes 的内建长期记忆底层是两个文件：

- `MEMORY.md`：偏环境事实、项目约定、工作经验、稳定结论
- `USER.md`：偏用户画像、沟通偏好、使用习惯、稳定约束

源码/文档明确事实：

它的实现不是简单文件读写，而是两套并行状态：

- 一套是“当前会话看到的冻结快照”，用于进入稳定提示词
- 一套是“实时可修改的最新状态”，用于接收本轮工具写入

来源：`tools/memory_tool.py`，`website/docs/user-guide/features/memory.md`

源码/文档明确事实：

这带来三个关键语义：

- agent 可以通过 `memory` tool 修改 memory / user 两个目标
- 修改会立即持久化到磁盘
- 当前活动 session 的 system prompt 不会因此重建；新内容通常要等到下一次 system prompt 重建时才进入稳定前缀，这既可能是开启全新会话，也可能是压缩后切换到新的 continuation session

来源：`tools/memory_tool.py`，`agent/conversation_compression.py`，`website/docs/user-guide/features/memory.md`，`website/docs/developer-guide/prompt-assembly.md`

基于实现的工程解释：

这是一种很典型的“**写时立即持久化，读时 session 级冻结快照**”设计。

## 4. 外部 Memory Provider 的 turn 节奏

Hermes 除了内建 `MEMORY.md / USER.md`，还支持外部 memory provider，例如 Honcho、Mem0、Hindsight、Supermemory 等。

源码/文档明确事实：

这里有两个实现细节要注意：

- 同一时间只允许 **一个** 外部 provider 激活
- 内建 memory 始终保留，外部 provider 是叠加层，不是替代层

来源：`agent/memory_manager.py`，`website/docs/user-guide/features/memory-providers.md`

源码/文档明确事实：

Hermes 对外部记忆系统采用统一的生命周期节奏：

- 会话开始或回合开始时，先拿一小段适合注入当前上下文的长期记忆
- 当前回合完成后，再把这轮用户输入和最终回复同步回外部记忆系统
- 有些外部记忆系统还会顺手为“下一轮可能用到的内容”做后台预热

来源：`agent/memory_manager.py`，`agent/conversation_loop.py`，`website/docs/user-guide/features/memory-providers.md`

基于实现的工程解释：

所以它不是“记忆系统自己在外面独立工作”，而是：

- 回合前帮助主流程回忆相关长期信息
- 回合后吸收刚刚发生的新信息
- 必要时在后台慢慢完成写入或预热

源码/文档明确事实：

还有一个重要约束：

- Hermes 只会在 turn 真正完成后再做 `sync_all(...)`
- 中断或未完成的 turn 不会被当作正式记忆写入外部 provider

来源：`agent/conversation_loop.py`，`run_agent.py::_sync_external_memory_for_turn()` 路径说明见既有调研，`docs/调研/Hermes-Agent-架构借鉴分析.md`

## 5. Session 设计与 Compression 的结合

基于实现的工程解释：

Hermes 的 session 不只是消息容器，它和 context compression 是强耦合的。

源码/文档明确事实：

压缩发生时，Hermes 会做两层事情：

第一层是消息级压缩：

- 保护 system prompt 和前几个 head messages
- 保护最近 tail messages
- 把中段历史压成结构化 summary

第二层是 session 级切换：

- 结束旧 session，结束原因标记为 `compression`
- 生成新的 session_id
- 创建新的 SQLite session 记录
- 通过 `parent_session_id` 把新 session 挂到旧 session 之下
- 把新 system prompt 写回新 session

来源：`agent/context_compressor.py`，`agent/conversation_compression.py`，`website/docs/developer-guide/context-compression-and-caching.md`，`website/docs/user-guide/sessions.md`

基于实现的工程解释：

这意味着 Hermes 的 compression 不是“原地覆盖历史”，而是：

- 旧 session 保留原始脉络
- 新 session 作为压缩后的 continuation 继续运行

基于实现的工程解释：

这个 lineage 设计主要是服务压缩后的继续运行和历史检索，不是多候选回复模型。

## 6. 历史消息搜索工具

源码/文档明确事实：

Hermes 的 `session_search` 不是简单全文检索，而是一条完整的“历史回忆流水线”。

它的核心链路是：

- 先在所有历史消息中做全文检索，得到按相关性排序的命中消息
- 再按 session 聚合，选 top N 个唯一会话
- 对每个会话加载完整 transcript
- 把 transcript 截断到大约 `100K chars`，但不是随便截，而是围绕 query 命中点选一个最佳窗口

来源：`tools/session_search_tool.py`，`website/docs/user-guide/sessions.md`

源码/文档明确事实：

这个“最佳窗口”选择有明确算法：

- 先找完整 query phrase 命中
- 如果没有，再找多个 query term 在 200 字符邻域内的共现位置
- 再不行，回退到单词级命中
- 最后在候选命中位置上选一个覆盖最多命中点的窗口

来源：`tools/session_search_tool.py::_truncate_around_matches`

源码/文档明确事实：

选出窗口后，Hermes 会：

- 把这个窗口交给一个更快、更便宜的辅助模型
- 用一个明确围绕当前 query 的总结提示，让它只提炼与当前问题相关的内容
- 返回 per-session 的 summary + metadata，而不是原始 transcript

来源：`tools/session_search_tool.py::_summarize_session`，`website/docs/user-guide/sessions.md`

基于实现的工程解释：

所以 `session_search` 的真实设计是：

- **FTS5 检索**
- **按 session 聚合**
- **最佳上下文窗口选择**
- **query-focused summary**

基于实现的工程解释：

它本质上是一个 recall 工具，而不是一个纯数据库搜索接口。

## 7. 提示词缓存优化策略

基于实现的工程解释：

Hermes 的 prompt caching 策略核心是“**稳定前缀优先**”。

源码/文档明确事实：

它做了几层配合：

来源：`agent/conversation_loop.py`，`agent/prompt_caching.py`，`gateway/run.py`，`website/docs/developer-guide/prompt-assembly.md`，`website/docs/developer-guide/context-compression-and-caching.md`

第一层：稳定提示词按会话复用

- 同一个会话里，稳定提示词尽量保持不变
- 如果这是一个被恢复或延续的会话，优先复用之前已经保存的版本
- 这样可以避免因为记忆文件变化而每轮重建提示词

第二层：稳定层和动态层分开

- 长期身份、规则、记忆快照这类内容放在稳定层
- 当前回合临时追加的引导、外部 recall、平台上下文补充放在动态层

基于实现的工程解释：

这样做的目的，是避免为了临时信息而破坏整段稳定前缀。

源码/文档明确事实：

第三层：面向 Anthropic 的前缀缓存策略

- 它会重点保护 system prompt 这一段
- 同时再把当前请求尾部最后几条非 system 消息也作为缓存断点

来源：`agent/prompt_caching.py`，`website/docs/developer-guide/context-compression-and-caching.md`

基于实现的工程解释：

- 这些尾部消息不是“永远不变”，而是在相邻几轮里通常高度重叠，代表当前正在处理的工作区
- 随着新消息不断追加，被重点保护的尾部窗口会持续向后滑动，所以可以把它理解成一个“滚动窗口”

源码/文档明确事实：

第四层：运行时对象也按会话复用

- 在消息平台场景下，Hermes 不会每来一条消息就完全新建一套 agent 状态
- 它会尽量复用这个会话对应的运行时对象，避免重复构建稳定提示词

来源：`gateway/run.py`

源码/文档明确事实：

第五层：压缩时尽量减少对缓存的破坏

- 压缩只改中段历史，不动最前面的稳定部分和最后面的活跃部分
- 稳定提示词最多只做很小、很少次数的说明性修改
- 压缩之后，中段缓存会失效，但最前面的稳定前缀仍然能保住
- 官方文档明确说明：压缩后，被压缩区域的缓存会失效，但 system prompt 缓存仍然保留，而尾部这个 3 条消息的滚动窗口通常会在后续 1 到 2 轮里重新建立起来

来源：`agent/context_compressor.py`，`website/docs/developer-guide/context-compression-and-caching.md`

源码/文档明确事实：

还有一个容易混淆但很重要的点：

- 压缩摘要本身是一次独立的辅助模型调用
- 它只总结中段历史，而不是把完整会话重新喂一遍

来源：`agent/context_compressor.py::_generate_summary`

基于实现的工程解释：

- Hermes 优化的重点是“压缩后主会话还能快速恢复缓存收益”，而不是“压缩这一次调用本身也要吃满缓存”

## 8. 值得借鉴的设计原则

基于实现的工程解释：

如果只提炼架构原则，Hermes 最值得借鉴的是：

- 用同步、可中断的单主循环承载核心生成链路
- 把 memory / recall / compression / delegation / cron 视为主循环外围能力
- 让长期记忆的“修改语义”和“prompt 注入语义”解耦
- 让 session persistence 成为 recall、compression、resume 的共同底座
- 把搜索做成 recall pipeline，而不只是数据库检索
- 把提示词缓存当成运行时架构约束来设计，而不是模型供应商提供的一个附加优化

## 9. 一句话总结

基于实现的工程解释：

Hermes 本质上是一个“**以同步主循环为核心，用会话、记忆、压缩、历史回忆和提示词缓存这些外围机制稳定支撑长对话运行**”的 agent 系统。它最强的地方不是某个单独功能，而是这些运行时能力之间的边界比较清晰，而且已经按真实产品运行约束打磨过。
