# Session 模块详细方案

## 目标

为一期后端补齐聊天主链路的数据骨架与会话边界，形成可直接落地的 `session` 模块方案。

本方案聚焦三件事：

- 明确 `session` 模块对 `sessions`、`messages`、`session_summaries` 的 owner 边界
- 明确聊天运行过程中消息如何通过 `SessionService` 写入与读取
- 收口 `retry`、`regenerate`、候选结果查看、标题更新、摘要写入等关键语义

该方案严格遵循当前一期已确认边界：

- 技术栈沿用 `FastAPI + PostgreSQL + Redis`
- `session` 是 `sessions`、`messages`、`session_summaries` 的 owner
- `chat`、`agent`、`recall`、`compression` 不直接跨模块拼 SQL 写这些表
- 聊天运行态仍以 Redis 为主，不单独新增持久化 run 主表
- 一期先保证主链路可落地，不提前引入复杂树状会话模型

## 设计范围

本方案覆盖：

- `sessions`、`messages`、`session_summaries` 的模块边界
- `SessionService` 的公开能力
- 会话创建、消息写入、消息读取、会话重命名
- `retry` 的覆盖语义
- `regenerate` 的候选结果语义
- assistant 回复组、候选结果、tool 消息之间的归属关系
- 会话详情、消息列表、候选详情接口的职责拆分
- 标题更新与标题生成入口预留
- 摘要写入边界与聚合字段维护规则

本方案暂不覆盖：

- session 删除
- 历史任意位置的复杂分支树切换
- 多层嵌套候选树
- 完整对话 DAG 可视化
- 独立搜索接口细节
- 更复杂的标题自动生成链路

## 与前序文档的修正关系

本方案对 `session` 相关设计做一次正式收口，并明确三份一期文档之间的对齐关系。

更早阶段曾讨论过如下思路：

- `regenerate` 创建子 session 分支
- 候选结果由 `sessions.parent_session_id`、`branch_point_message_id` 等元数据解释

本方案确认后的新结论是：

- 一期不采用“`regenerate` 创建子 session”方案
- 一期采用“单 session 内，某个 assistant 回复组挂多个候选结果”的方案
- `retry` 与 `regenerate` 的差异不再体现在是否创建子 session，而体现在“覆盖旧结果”还是“保留多个候选结果”
- 但对于长会话 compression，可单独引入基于 `parent_session_id` 的 continuation / lineage 方案，其语义与 `regenerate` 解耦

也就是说：

- `retry`：直接覆盖最近一个 assistant 主结果
- `regenerate`：在最近一个 assistant 回复组下新增候选结果，并保持“唯一主结果”

因此本方案应视为：

- 对 `session` 模块详细设计阶段的正式收口
- 对早期 session 分支语义讨论的一次定稿修正

需要同步理解的是：

- 当前 `02-后端最小落地架构.md`、`03-数据库设计草案.md` 与本文应统一按“regenerate 采用单 session + assistant 回复组候选集；compression 允许采用 continuation lineage”的方案理解
- 一期 `regenerate` 的核心语义已经统一收口到 `messages.response_group_id`、`is_current_response`、`response_locked_at` 等字段，而不是放在 `sessions` 分支字段上
- 如果后续继续细化数据库 DDL，应优先把候选结果语义补到 `messages` 侧；而 `sessions.parent_session_id` 只为 compression continuation / lineage 服务

## 总体思路

一期采用“regenerate 走单 session 主链 + assistant 回复组候选集；compression 走 continuation lineage”的混合模型。

具体来说：

- 一个 `session` 表示一段完整会话的元数据容器
- 一个逻辑会话由一个 root session 和若干 continuation session 组成
- `messages` 表保存该会话内所有消息，包括主链消息、候选 assistant 消息、tool 调用消息、tool 结果消息
- 主链消息按 `sequence_no` 严格递增排列，是用户默认阅读到的消息骨架
- 某一条 assistant 主结果可以拥有多个候选结果
- 候选结果不进入主链默认展示，但保留独立查看能力
- 每个 assistant 回复组始终有且仅有一个主结果
- 当用户基于某个候选结果继续发言时，该候选立即转正为主结果，并锁定该回复组，不再允许切换主结果
- 当会话过长触发正式 compression 时，可创建一个新的 continuation session，并通过 `parent_session_id` 指向父 session
- 所有 continuation session 共享同一个 `root_session_id`，前端按 `root_session_id` 聚合为一个连续会话框

这样做的目的：

- 避免一期过早引入复杂 session 分支树
- 保持 `retry` 与 `regenerate` 的用户心智接近
- 保持 `session` 模块对消息主骨架的解释成本可控
- 为前端提供“主链查看 + 候选详情查看”的清晰接口模型
- 同时保留长会话 lineage、回溯与跨 session 精准检索能力

## 模块职责边界

### `session` 模块职责

`session` 模块负责会话真源与消息真源。

建议职责：

- 创建会话
- 读取会话列表与会话元数据
- 读取主链消息
- 读取某个 assistant 回复组下的候选结果详情
- 写入用户消息、assistant 消息、tool 消息、summary 消息
- 维护 assistant 回复组与候选结果的归属关系
- 执行最近回复组的 `retry` 覆盖
- 执行最近回复组的 `regenerate` 候选追加与主结果切换
- 维护 `sessions.message_count`、`tool_call_count`、`input_tokens`、`output_tokens`、`last_message_at`
- 统一管理 `session_summaries` 的写入
- 维护 root session、continuation session 与当前 tip session 的关联
- 提供标题更新与标题生成入口

`session` 模块不负责：

- HTTP 流式输出
- run 生命周期控制
- 模型选择
- prompt 组装
- tool 实际执行
- recall 策略决策
- compression 策略决策

这些职责分别属于 `chat`、`agent`、`models`、`tools` 等模块。

### 其他模块如何进入 `session`

统一做法：

- `chat` 通过 `SessionService` 创建用户消息与读取消息
- `agent` 通过 `SessionService` 写 assistant 与 tool 消息
- `recall` / `compression` 通过 `SessionService` 写 `session_summaries`
- 前端只通过 `session` 模块暴露的 HTTP API 读取会话与消息

要求：

- 不允许其他模块直接跨模块写 `sessions`、`messages`、`session_summaries`

## 推荐目录结构

建议目录如下：

```text
backend/
  app/
    modules/
      session/
        api.py
        service.py
        repository.py
        domain.py
        schemas.py
```

说明：

- `session/api.py` 暴露 `/api/v1/sessions/*`
- `session/service.py` 负责会话读写编排、消息写入、`retry/regenerate`、聚合字段更新、标题入口、summary 管理
- `session/repository.py` 负责 `sessions`、`messages`、`session_summaries` 的数据库读写
- `session/domain.py` 负责 `Session`、`Message`、`AssistantResultSlot` 等最小领域语义
- `session/schemas.py` 负责列表、详情、消息、候选详情、重命名等接口模型

## 核心对象

### Session

沿用已有领域对象，并强调它只表示会话容器与统计元数据：

- `id`
- `user_id`
- `parent_session_id`
- `root_session_id`
- `title`
- `status`
- `active_model_provider`
- `active_model_name`
- `message_count`
- `tool_call_count`
- `input_tokens`
- `output_tokens`
- `started_at`
- `ended_at`
- `last_message_at`

本方案中，一期不再使用以下字段：

- `branch_point_message_id`
- `branch_status`
- `is_listed_in_session_list`
- `branch_locked_at`

原因：

- 一期不再用子 session 表达 `regenerate`
- 这些字段不再承担一期候选结果语义的核心职责
- 一期 assistant 回复组与候选结果改由 `messages` 侧建模，不再由 `sessions` 分支字段表达

其中，`parent_session_id` 建议重新引入，但语义严格限定为：

- 仅服务 compression continuation / lineage
- 不服务 `retry/regenerate`
- 不表达候选结果切换

同时建议引入：

- `root_session_id`

其语义是：

- 标识同一个逻辑会话的起点
- root session 自己的 `root_session_id = id`
- 所有 continuation session 继承相同 `root_session_id`
- 前端会话框、会话列表聚合、当前 tip 定位都优先基于 `root_session_id`

### Message

`Message` 仍然是会话中最细粒度的持久化消息对象。

建议保留已有核心字段：

- `id`
- `session_id`
- `assistant_message_id`
- `role`
- `message_type`
- `content_text`
- `content_json`
- `tool_name`
- `tool_call_id`
- `tool_calls`
- `reasoning_text`
- `reasoning_details`
- `token_count_input`
- `token_count_output`
- `sequence_no`
- `is_hidden`
- `created_at`

在本方案里，这些字段的职责进一步收口为：

- `sequence_no`：主链读取顺序依据，严格递增
- `assistant_message_id`：tool 消息归属到所属 assistant 结果消息的重要挂载点
- `is_hidden`：仅作为展示辅助字段，不作为候选分组主语义

### Assistant Response Group

一期建议在 `session` 模块概念上引入“assistant 回复组”。

它不是必须暴露给前端的数据库表名，而是一个稳定业务语义：

- 一次用户提问后，对应一个 assistant 回复组
- 这个回复组上始终存在一个主结果
- 这个回复组上可选存在多个候选结果
- `retry` 作用在该回复组的主结果上
- `regenerate` 作用在该回复组上新增候选结果

这能把“线性消息流”与“同一位置的多候选结果”区分开。

### Candidate Message

候选结果的本质仍然是 `messages` 表中的 message，只是它不是主链默认展示结果。

候选结果特点：

- 候选结果与主结果属于同一个 assistant 回复组
- 候选结果也可以拥有自己的 tool 消息轨迹
- 候选结果默认不在 `/messages` 主链内容中完整展开
- 候选结果仅通过候选详情接口查看

## 关键语义收口

### 1. `retry`

`retry` 一期收口为：

- 仅允许对最近一个 assistant 主结果执行
- 不创建子 session
- 不创建新的 assistant 主消息记录
- 直接物理覆盖原 assistant 主消息的内容
- 覆盖后仍沿用同一个 `message_id`

也就是说：

- 前端看到的是“同一个回复位置重新生成了内容”
- 数据库里也是“同一条 message 被更新”

这样做的优点：

- 语义最贴近“重试当前回复”
- 不增加一期的消息版本链复杂度
- 不要求前端处理“同一个位置多条重试历史”

风险与约束：

- 旧 assistant 内容会丢失
- 为保留最小审计能力，应至少记录一次覆盖事件
- 审计可通过 `audit_logs` 或最小 revision 方式记录 before/after 摘要

### 2. `regenerate`

`regenerate` 一期收口为：

- 仅允许作用于最近一个 assistant 回复组
- 不创建子 session
- 在同一个 session 内保留多个候选 assistant 结果
- 候选结果与主结果属于同一个 assistant 回复组
- 同一回复组始终有且仅有一个主结果

与 `retry` 的差异：

- `retry`：覆盖旧主结果
- `regenerate`：保留多个可选结果

### 3. 候选结果转正与锁定

当用户基于某个候选结果继续发出下一条用户消息时：

- 该候选立即转正为主结果
- 原主结果降为历史候选
- 该 assistant 回复组进入锁定状态
- 锁定后不再允许切换主结果
- 其他候选结果仍保留历史查看能力，但不再可回切为主结果

锁定触发点明确为：

- 用户继续发言即锁定
- 不要求等下一轮 assistant 成功返回后再锁定

### 4. 工具消息归属

一期确认：

- tool call / tool result 也进入 `messages` 表
- 它们属于 session 模块统一管理的消息真源

归属规则：

- tool 消息通过 `assistant_message_id` 挂到其所属的 assistant 结果消息上
- 主结果的 tool 轨迹挂到主结果 message
- 候选结果的 tool 轨迹挂到对应候选 message

这样做的好处：

- 候选详情可以稳定还原各自的 tool 过程
- 主链与候选链路的 tool 归属清晰

### 5. compression continuation

当单个 session 历史过长，正式触发 compression 时，建议：

- 由 `CompressionService` 生成一条 `compression_summary`
- 通过 `SessionService` 持久化该摘要
- 创建一个新的 continuation session
- 新 session 的 `parent_session_id` 指向被压缩的父 session
- 新 session 继承父 session 的 `root_session_id`
- continuation session 以压缩摘要和保留尾部消息作为新的运行起点

这里要明确区分：

- 这是 session continuation，不是 regenerate candidate
- continuation session 的目的是承接长会话运行，而不是表达同一回复位置的多个候选答案

这样做的价值是：

- 长会话回溯性更强
- 更利于沿 lineage 做跨 session recall 和精准检索
- 压缩前后的边界更清晰

为什么不仅要有 `parent_session_id`，还要给 `compression_summary` 补结构字段：

- 仅有 `parent_session_id` 只能说明“这个 session 接在那个 session 后面”。
- 但它无法说明“压缩时到底压掉了父 session 的哪一段消息”。
- 也无法说明“哪些最后几轮消息作为 tail 被原样带到了 continuation session”。
- 更无法稳定建立“这一个 continuation session 对应哪一条 compression summary”的双向关系。

因此建议 `compression_summary` 至少记录：

- `source_session_id`
- `target_session_id`
- `source_message_range_start`
- `source_message_range_end`
- `tail_preserved_from_seq`

这些字段的价值不是为了展示更多元数据，而是为了：

- 让 lineage 调试、跨 session recall、会话拼接和压缩点审计真正可做
- 让后续代码能精确知道“summary 覆盖区”和“tail 保留区”的边界

### 6. root session、tip session 与消息拼接

为了让“底层多个物理 session、前端一个会话框”成立，建议明确三个概念：

- `root session`：整条逻辑会话的起点 session
- `continuation session`：compression 产生的后续物理 session
- `tip session`：当前仍在继续写入消息的最新 session

推荐规则：

- root session 的 `root_session_id = id`
- continuation session 的 `root_session_id = root.id`
- continuation session 的 `parent_session_id = 上一个物理 session.id`
- 当前对话输入总是写入 tip session
- 会话列表默认按 `root_session_id` 聚合，只显示一个逻辑会话卡片

消息拼接建议：

- 查询当前会话框时，不按单个 `session_id` 读取
- 而是先按 `root_session_id` 找到整条 lineage 上的所有物理 session
- 再按 continuation 顺序拼接每个物理 session 的主链消息
- 候选结果仍然只在各自物理 session 内，通过 `response_group_id` 解释
- 当前继续聊天时，先根据 `root_session_id` 解析 tip session，再把新消息写入 tip session

也就是说：

- `parent_session_id` 解决“这一段接在上一段后面”
- `root_session_id` 解决“这些段本质上属于同一个会话框”

### 7. compression continuation 时序

建议把 compression continuation 的主流程正式收口为：

1. `CompressionService` 判断当前 tip session 已达到压缩阈值
2. 读取当前 tip session 的完整主链消息
3. 计算压缩边界：
   - 保护 head
   - 保护 tail
   - 中间区域作为 summary 覆盖区
4. 生成一条 `compression_summary`
5. 通过 `SessionService.save_compression_summary(...)` 持久化该摘要，并写明：
   - `source_session_id`
   - `source_message_range_start`
   - `source_message_range_end`
   - `tail_preserved_from_seq`
6. `SessionService.create_compression_continuation(...)` 创建新的 continuation session：
   - `parent_session_id = 旧 tip session.id`
   - `root_session_id = 旧 tip session.root_session_id`
7. 将刚生成的 `compression_summary.target_session_id` 回填为新 continuation session.id
8. 把父 session 的保留 tail 复制或投影到 continuation session 的初始上下文中
9. 将当前逻辑会话的活跃写入位置切换到新 tip session
10. 用户下一条消息开始写入新的 tip session，但前端仍停留在同一个会话框

需要明确：

- 被压缩的是父 tip session 内的可压缩中段，而不是整条逻辑会话的所有历史
- continuation session 不是“只拿一条 summary 空启动”
- continuation session 的起点应为“compression summary + 保留 tail”

## 数据建模建议

### 为什么现有 `messages` 字段还不够

如果一期采用“单 session、多候选 assistant 回复组”，仅靠现有字段很难清晰表达：

- 哪些 message 属于同一个 assistant 回复组
- 哪一条是当前主结果
- 哪些是历史候选结果
- 某个回复组是否已锁定

因此本方案建议：

- 候选结果仍放在 `messages` 表
- 但需要补充用于“回复组归组”和“主结果选择”的字段

### 建议新增的消息语义字段

建议在 `messages` 表上新增以下语义字段：

- `response_group_id`：assistant 回复组归组标识
- `is_current_response`：该 message 是否为当前主结果
- `response_locked_at`：该回复组是否已锁定的时间点

建议说明：

- `response_group_id` 只对 assistant 结果消息和挂在其下的 tool 消息有意义
- 同一回复组下的 assistant 主结果与候选结果共享同一个 `response_group_id`
- 候选自己的 tool 消息也可继承同一个 `response_group_id`，便于聚合查询
- `role = 'assistant' and is_current_response = true` 表示该 assistant 结果是当前主结果
- `role = 'assistant' and is_current_response = false` 表示该 assistant 结果是同一回复组下的候选结果
- `tool` 消息不参与主结果判定，只通过 `assistant_message_id` 和 `response_group_id` 归属到对应 assistant 结果
- 同一 `response_group_id` 下应当始终只有一个 assistant 结果 `is_current_response=true`
- `response_locked_at` 可挂在主结果 message 或独立抽象到回复组层，但一期为了减少新表数量，可先用 message 维度表达

如果你不想在 `messages` 上堆太多字段，也可以在实际实现时抽一张辅助表，例如：

- `message_result_slots`

但从一期最小落地角度，先在 `messages` 补字段通常更轻。

### 建议新增的约束方向

为了表达“唯一主结果”，建议增加应用层或数据库层约束：

- 同一 `response_group_id` 下，只允许一个 assistant 结果 `is_current_response=true`
- 候选结果必须与主结果属于同一 `session_id`
- tool 消息的 `assistant_message_id` 必须指向与自身同 `session_id` 的 assistant 结果消息
- 锁定后的回复组禁止再次切换主结果

其中：

- “唯一主结果”适合用部分唯一索引或应用层写入保护
- “锁定后禁止切换”更适合应用层保证

## 接口设计

### 1. `GET /api/v1/sessions`

用途：

- 返回当前登录用户的会话列表

返回粒度：

- 返回逻辑会话列表，而不是所有物理 session 列表
- 不返回完整消息历史
- 不返回候选详情

建议字段：

- `root_session_id`
- `tip_session_id`
- `title`
- `status`
- `active_model_provider`
- `active_model_name`
- `message_count`
- `last_message_at`
- `started_at`

### 2. `GET /api/v1/sessions/{session_id}`

用途：

- 返回单个逻辑会话的元数据

参数语义建议：

- 路由中的 `{session_id}` 一期按逻辑会话 ID 解释，也就是 `root_session_id`
- 物理 continuation session 的 `id` 不作为前端会话框主键直接暴露

已确认收口：

- 仅返回 session 元数据
- 不直接返回完整消息历史

建议字段：

- `root_session_id`
- `tip_session_id`
- `title`
- `status`
- `active_model_provider`
- `active_model_name`
- `message_count`
- `tool_call_count`
- `input_tokens`
- `output_tokens`
- `started_at`
- `ended_at`
- `last_message_at`

### 3. `GET /api/v1/sessions/{session_id}/messages`

用途：

- 返回该逻辑会话的聚合主链消息

参数语义建议：

- 路由中的 `{session_id}` 一期同样按 `root_session_id` 解释

返回规则：

- 先按 `root_session_id` 找整条 lineage
- 再按物理 session 顺序和各自 `sequence_no` 正序分页返回
- 默认返回主链消息 + 候选摘要
- 不直接展开候选消息全文
- 不直接展开候选工具轨迹

消息节点建议携带的候选摘要字段：

- `response_group_id`
- `current_response_message_id`
- `candidate_count`
- `is_response_locked`

说明：

- 这里的“候选摘要”只返回轻量标识信息，不返回完整候选消息体
- 候选完整内容由单独接口查询

### 4. `GET /api/v1/sessions/{session_id}/messages/{message_id}/candidates`

用途：

- 查看某条 assistant 主结果所在回复组下的所有候选结果

返回内容建议：

- 该回复组下所有 assistant 结果
- 每个结果的是否为当前主结果
- 每个结果的简要文本
- 每个结果对应的 tool 轨迹摘要或详情
- 当前回复组是否已锁定

说明：

- 这是一期新增的候选详情接口建议
- 前端只有在用户点击“查看候选结果”时才需要调用

### 5. `POST /api/v1/sessions/{session_id}/rename`

用途：

- 更新会话标题

说明：

- 一期仍保留该接口
- 建议记录 `session rename` 审计日志

## 内部服务方法边界

建议 `SessionService` 至少暴露以下能力：

- `create_session(user_id, model_route) -> Session`
- `get_session(user_id, session_id) -> Session`
- `get_root_session(user_id, root_session_id) -> Session`
- `get_tip_session(user_id, root_session_id) -> Session`
- `list_sessions(user_id, page) -> SessionList`
- `list_lineage_sessions(user_id, root_session_id) -> SessionList`
- `list_session_messages(user_id, session_id, cursor) -> MessagePage`
- `list_conversation_messages(user_id, root_session_id, cursor) -> MessagePage`
- `list_message_candidates(user_id, session_id, message_id) -> CandidateList`
- `append_user_message(...) -> Message`
- `append_assistant_message(...) -> Message`
- `append_tool_call_message(...) -> Message`
- `append_tool_result_message(...) -> Message`
- `overwrite_last_assistant_message_for_retry(...) -> Message`
- `append_regenerate_candidate(...) -> Message`
- `select_candidate_and_lock_on_continue(...) -> None`
- `rename_session(user_id, root_session_id, title) -> Session`
- `update_session_title(user_id, root_session_id, title) -> Session`
- `generate_session_title_input(root_session_id) -> TitleContext`
- `save_session_summary(...) -> SessionSummary`
- `save_compression_summary(...) -> SessionSummary`
- `create_compression_continuation(...) -> Session`
- `resolve_root_session_id(session_id) -> SessionId`
- `attach_compression_summary_target(summary_id, target_session_id) -> None`
- `rebuild_session_aggregates(session_id) -> None`

说明：

- 这里未显式带 `root_` 前缀的方法，默认用于物理 session 内部操作；带 `root_session_id` 的方法用于逻辑会话聚合语义。
- `generate_session_title_input` 只是为标题生成提供入口或上下文，不要求 `session` 模块内部直接调用大模型
- 标题真正生成可由后续 `chat` 或 `agent` 编排链路调用后再回写

## 消息写入时机

这里的“写入时机”指的是：

- `chat` / `agent` 运行过程中，通过 `SessionService` 何时把消息落到数据库

不是指：

- `session` 模块对前端暴露多少写接口

一期确认采用：

- 运行中渐进落库

具体建议：

1. 收到用户消息后立即落库
2. assistant 开始生成后，在可稳定写入的时机创建 assistant 消息
3. tool call / tool result 在运行过程中逐步写入
4. 最终完成后补齐 token、状态、统计字段

这样做的原因：

- 便于中断恢复
- 便于 stop / cancel 后保留已产生的消息痕迹
- 便于审计和问题排查
- 与工具调用日志、运行态治理更一致

## `sequence_no` 规则

一期确认：

- `messages.sequence_no` 采用全量占号规则

也就是说：

- 所有实际落库消息都占用严格递增的 `sequence_no`
- 包括用户消息、assistant 消息、tool 消息、隐藏消息

优点：

- 排序规则单一
- 调试和审计更直接
- 不需要为“隐藏消息是否编号”维护第二套顺序体系

补充说明：

- 候选 assistant 消息如果不属于主链默认展示，也仍然建议占号
- 但 `/messages` 主接口可以根据主链选择规则过滤不展示这些候选完整内容

## 摘要写入边界

一期确认：

- `session_summaries` 由 `SessionService` 统一写入与管理

这意味着：

- `recall` / `compression` 不直接写 `session_summaries` 表
- 它们只把结果提交给 `SessionService`
- `SessionService` 负责版本推进、归属校验、落库与必要聚合处理

这样做的目的：

- 保持 `session` 模块对会话摘要真源的 owner 地位
- 避免其他模块绕过边界直接改表

## 标题生成能力

一期关于标题的收口是：

- `session` 模块需要预留标题能力
- 但不要求 `SessionService` 内部直接负责模型调用

建议做法：

- `SessionService` 提供标题更新入口
- `SessionService` 提供标题生成所需上下文或输入组装入口
- 标题生成动作可由后续上游链路调用大模型后再回写

这样可以兼顾：

- 先把 `session` 作为标题真源 owner 立住
- 又不在一期把模型编排强塞进 `session` 内部

## 聚合字段维护规则

一期继续沿用总方案：

- `SessionService` 单点维护 `message_count`、`tool_call_count`、`input_tokens`、`output_tokens`、`last_message_at`

建议规则：

- 每次写 message 时同步更新或延迟小步更新
- `tool_call_count` 仅统计工具调用相关消息或工具调用事件数，需在实现时固定一个口径
- `last_message_at` 以最近一条真实落库消息时间为准
- 提供离线重建能力作为兜底

补充约束：

- `retry` 物理覆盖原 assistant 消息时，不应错误增加 `message_count`
- `regenerate` 新增候选结果时，是否计入 `message_count` 需在实现时统一口径

从当前设计出发，更推荐：

- 只要真实新增了一条 `messages` 记录，就计入 `message_count`

这样统计口径更稳定，也更贴近真实存储量。

## 分页与查询建议

一期确认：

- `GET /sessions/{session_id}/messages` 一期就做分页

建议方式：

- 基于 `sequence_no` 做正序分页或游标分页

建议原因：

- 聊天记录理论上会持续增长
- 后面还有候选摘要、tool 消息、隐藏消息等聚合逻辑
- 尽早采用分页更能避免接口重构

## 错误与约束建议

建议至少定义以下 `session` 级错误语义：

- `SESSION_NOT_FOUND`
- `SESSION_ACCESS_DENIED`
- `SESSION_RENAME_INVALID`
- `SESSION_MESSAGE_NOT_FOUND`
- `SESSION_RETRY_NOT_ALLOWED`
- `SESSION_REGENERATE_NOT_ALLOWED`
- `SESSION_CANDIDATE_NOT_FOUND`
- `SESSION_CANDIDATE_SWITCH_LOCKED`
- `SESSION_RESULT_SLOT_INVALID`

建议规则：

- `retry` 仅允许最近一个 assistant 主结果
- `regenerate` 仅允许最近一个 assistant 回复组
- 锁定后的回复组禁止再次切换主结果
- 候选详情接口必须校验该 message 属于当前 session 且属于当前用户

## 与其他模块的协作方式

### 与 `chat`

- `chat` 负责接收 HTTP 请求、流式输出、stop/retry/regenerate 入口
- `chat` 不直接写 `sessions/messages`
- `chat` 通过 `SessionService` 完成用户消息、会话读取和部分消息回写

### 与 `agent`

- `agent` 负责模型主循环和工具编排
- `agent` 通过 `SessionService` 写 assistant 与 tool 消息
- `agent` 在继续对话前应尊重回复组锁定语义

### 与 `tools`

- `tools` 模块维护工具执行与 `tool_invocations`
- `session` 模块维护工具消息在会话里的归属与展示真源

### 与 `recall` / `compression`

- `recall` / `compression` 产出摘要内容
- `SessionService` 负责统一写入 `session_summaries`

## 推荐实现顺序

为了尽快落地，建议按下面顺序开发：

1. 完成 `SessionRepository` 的会话与消息基础查询能力
2. 完成 root session / tip session 解析能力，以及逻辑会话聚合查询能力
3. 完成 `SessionService` 的创建会话、读取会话、重命名能力
4. 完成用户消息、assistant 消息、tool 消息的渐进写入能力
5. 完成 `sequence_no` 分配与聚合字段维护
6. 完成 `/sessions/{session_id}` 与 `/messages` 分离读取接口
7. 完成候选回复组的归组字段与唯一主结果约束
8. 完成候选详情接口
9. 完成最近回复组的 `retry` 覆盖语义
10. 完成最近回复组的 `regenerate` 与锁定语义
11. 完成 `session_summaries` 统一写入入口
12. 完成 compression continuation、tail 保留与 tip 切换逻辑

## 本方案的最终收口

一期 `session` 模块的最终方案建议收口为：

- 使用 `session` 模块承载会话、消息、摘要的真源边界
- 一期不采用 `regenerate` 创建子 session 的方案
- 一期采用“单 session + assistant 回复组多候选”方案
- 一期可对 compression 单独采用 `parent_session_id` continuation / lineage 方案
- `retry` 仅作用于最近一个 assistant 主结果，并做真正物理覆盖
- `regenerate` 仅作用于最近一个 assistant 回复组，并保留多个候选结果
- 同一回复组始终只有一个主结果
- 用户基于候选继续发言时，该候选立即转正并锁定回复组
- `messages` 表统一承载用户消息、assistant 消息、tool 消息与候选结果
- 主消息接口返回主链消息与候选轻摘要，候选详情通过单独接口读取
- 主会话框读取建议按 `root_session_id` 聚合整条 lineage，而不是只读单个物理 `session_id`
- `GET /sessions/{session_id}` 仅返回 session 元数据
- `GET /sessions/{session_id}/messages` 一期即支持分页
- `session_summaries` 由 `SessionService` 统一写入与管理
- `parent_session_id` 只承接 compression continuation / lineage，不承接 `regenerate` 候选语义
- `root_session_id` 作为整个逻辑会话的稳定标识，承接“一个会话框下多个 continuation session”的聚合语义
- 标题生成能力在 `session` 模块预留入口，但模型调用由上游编排决定

这套设计满足你当前的一期目标：

- 比子 session 分支树更轻
- 比完全覆盖式消息流更能保留 regenerate 候选体验
- 比纯单 session 压缩更利于保留 lineage 与跨 session 检索脉络
- 保持了 `session` 作为聊天数据骨架 owner 的边界清晰
- 能直接支撑后续 `chat`、`agent`、`tools`、`recall`、`compression` 模块落地
