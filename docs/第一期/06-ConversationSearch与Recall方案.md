# ConversationSearch 与 Recall 方案

## 目标

为 EchoMind 一期补齐跨会话检索与历史召回能力设计，形成一套既能支撑当前 Agent Runtime，又能与现有 `session / compression / continuation / memory / profile` 架构一致协作的正式方案。

本方案重点解决：

- 当用户提到“之前聊过的内容”时，系统如何稳定回忆
- 当单个逻辑会话已被 compression 拆成多个 continuation session 后，如何仍以“一个会话框”的方式检索历史
- `session_summaries`、原始 `messages`、`root_session_id`、`parent_session_id` 在检索链路中如何分工
- 一期应采用什么检索形式最合适
- 后续如果引入向量库，应该如何平滑演进

## 设计结论

EchoMind 的 `ConversationSearchService` 最适合采用：

- `session_summaries` 候选召回
- `messages` 证据回捞
- `root_session_id` 逻辑会话聚合
- focused recall summary 结果生成

更具体地说，一期最推荐采用：

- **第一层：summary-first candidate recall**
  - 先从 `session_summaries` 中找相关逻辑会话候选
- **第二层：message-level evidence drilldown**
  - 再到候选逻辑会话下的原始 `messages` 中找具体证据片段
- **第三层：recall result assembly**
  - 将逻辑会话摘要、命中片段、必要元数据整理成 recall 结果

这比直接照搬 Hermes 的“全库 message FTS -> session 聚合 -> focused summary”更适合 EchoMind，因为 EchoMind 已经具备：

- `root_session_id`
- `parent_session_id`
- `session_summaries`
- `compression_summary`
- continuation lineage

也就是说，EchoMind 可以先利用 summary 中间层缩小候选范围，再对少量逻辑会话做 message-level 精搜，而不是从一开始就全库扫描所有原始消息。

## 与 Hermes 的关系

### Hermes 已验证有效的部分

Hermes 的 `session_search_tool` 做了这些事情：

- 全局 FTS 搜索历史 `messages`
- 从命中的 message 反推出对应 session
- 对 child session / continuation session 做 lineage 归一化
- 读取对应 session transcript
- 围绕 query 选一个最相关的窗口
- 生成 focused summary 返回给主 agent

Hermes 值得借鉴的核心思想包括：

- 历史召回应独立于 memory
- 历史搜索应先找证据，再做总结
- recent mode 和 search mode 应分开
- 当前会话 lineage 应排除，不把当前 prompt 已知内容再召回一次

### EchoMind 不直接照搬的部分

EchoMind 不建议完全照搬 Hermes 的全库 message-first 路径，原因是：

- EchoMind 已经设计了 `session_summaries` 作为 compression / recall 的正式中间真源
- EchoMind 已经把逻辑会话与物理 continuation session 分开
- EchoMind 是服务端后端，不是单纯的本地 agent 工具系统

因此 EchoMind 更适合采用：

- **summary-first** 缩候选
- **message-second** 取证据
- **root-session aggregated** 组织结果

## 术语定义

### 1. 逻辑会话

逻辑会话是前端看到的“一个会话框”，由：

- 一个 root session
- 零个或多个 continuation session

共同组成。

逻辑会话的稳定标识为：

- `root_session_id`

### 2. 物理 session

物理 session 是数据库 `sessions` 表中的单条记录。

它可能是：

- root session
- continuation session

### 3. continuation lineage

当 compression 发生后：

- 父 session 结束写入
- 创建新的 continuation session
- 新 session 通过 `parent_session_id` 指向父 session

一条逻辑会话下的多个物理 session 构成一条 continuation lineage。

### 4. session summary

`session_summaries` 中存放的是会话摘要中间层，不是简单 UI 摘要。

常见类型包括：

- `session_summary`
- `compression_summary`
- `recall_summary`

### 5. evidence span

evidence span 指在原始 `messages` 中被检索命中的具体历史片段。

它是 recall 链路里的“证据层”，而不是最终返回给主模型的唯一形式。

### 6. focused recall summary

focused recall summary 指：

- 围绕当前 query
- 对某个逻辑会话的相关历史内容
- 生成的一段定向回顾摘要

它的目标不是概括整个会话，而是回答：

- 与当前 query 最相关的历史里，当时发生了什么

## 总体架构

推荐整体流程如下：

```text
User Query
  -> ConversationSearchService
     -> summary candidate recall
     -> root_session_id aggregation
     -> message evidence drilldown
     -> recall result assembly
  -> RecallService
     -> select / compress returned search results
     -> inject into current agent run
```

这里建议把两层能力分开：

- `ConversationSearchService`
  - 负责查历史，拿候选逻辑会话和证据片段
- `RecallService`
  - 负责在当前 run 中决定是否要调用搜索、如何压缩结果、如何注入 prompt

这符合你当前的模块边界：

- `session` 仍然是消息与摘要真源 owner
- `ConversationSearchService` 读取 `session` 数据，不跨模块直接改写其真源
- `RecallService` 是运行时编排层能力

## 一期推荐方案

### 方案名

**Summary-first candidate recall + message evidence drilldown**

### 第一层：candidate recall

输入 query 后，先从 `session_summaries` 中找候选逻辑会话。

推荐优先级：

1. `session_summary`
2. `compression_summary`
3. `recall_summary`

原因：

- `session_summary` 更像逻辑会话的高层概览
- `compression_summary` 保留了被压掉中段的信息
- `recall_summary` 偏运行时临时产物，价值次于前两者

这层的目标不是直接回答，而是：

- 快速找出最可能相关的 `root_session_id`

### 第二层：evidence drilldown

对候选 `root_session_id`：

1. 找到该 root 下的所有物理 session
2. 读取这些 session 的原始 `messages`
3. 用关键词 / FTS / trigram 做精细命中
4. 取出具体 evidence spans

这一步借鉴 Hermes 的核心思路：

- 不只看 summary
- 需要有真实原始消息证据

但比 Hermes 更进一步：

- 不是从全库一开始搜所有 message
- 而是先 summary 缩小范围，再做 message 精搜

### 第三层：结果组织

最终结果按 `root_session_id` 聚合，形成逻辑会话级搜索结果。

每条结果包含：

- 逻辑会话标识
- tip session 标识
- 时间信息
- source 信息
- title
- focused recall summary
- matched spans

## 为什么不直接采用全量 message-first 搜索

虽然 Hermes 的 message-first 搜索路径是可行的，但 EchoMind 一期不推荐直接照搬。

原因：

### 1. 你已经有 `session_summaries`

这是 Hermes 没有被服务化利用到同等程度的优势。

既然已经设计了：

- `session_summary`
- `compression_summary`

就应该先利用它们做低成本候选召回。

### 2. 全量 message-first 成本更高

随着历史增长：

- `messages` 数量远大于 `session_summaries`
- tool output 和噪声更多
- message 粒度更碎

一期直接从全库 message 搜到尾，成本和复杂度都更高。

### 3. summary-first 更能体现 continuation 架构的价值

你现在采用了：

- continuation session
- compression summary
- root 聚合

如果不先利用 summaries，等于把这套设计优势浪费掉了。

## 为什么不能只靠 summaries

虽然 summary-first 很重要，但也不能只停在 summaries。

原因是：

- summary 是压缩表示，不是原文
- 它不完全映照 query
- 某些精细化问题只存在于原始消息中

例如：

- 精确错误码
- 文件路径
- 命令行片段
- 用户原话
- 某段被 summary 略过的细节

因此一定要保留第二层：

- 在候选逻辑会话内回捞原始 `messages` 的 evidence spans

## 检索模式设计

### 1. recent mode

适用场景：

- 用户问“最近我们做了什么”
- 用户问“最近有哪些会话”
- 用户没有给出明确 query，只想浏览近况

策略：

- 不做全文搜索
- 按 `root_session_id` 聚合逻辑会话
- 按 tip session 的最近活跃时间倒序

这里建议 recent 的定义是：

- 最近活跃的逻辑会话
- 而不是最近创建的物理 session

### 2. search mode

适用场景：

- 用户给出具体 query
- agent 判断需要回忆跨会话历史

策略：

1. summaries 检索候选
2. 聚合为 `root_session_id`
3. messages 证据回捞
4. 生成 focused recall summary

## candidate recall 设计

### 输入

建议输入：

- `user_id`
- `query`
- `limit`
- `exclude_root_session_id` 可选
- `time_range` 可选
- `role_filter` 可选

### 输出

建议返回候选：

```json
[
  {
    "root_session_id": 1001,
    "score": 0.91,
    "matched_summary_types": ["session_summary", "compression_summary"]
  },
  {
    "root_session_id": 1042,
    "score": 0.84,
    "matched_summary_types": ["session_summary"]
  }
]
```

### 实现方式

一期建议：

- PostgreSQL FTS 搜 `session_summaries.summary_text`
- 应用层按 `root_session_id` 聚合去重

二期建议增强：

- 对 `session_summaries` 做 embedding
- 引入 summary 向量召回
- 和 FTS 结果融合排序

## evidence drilldown 设计

### 输入

- `root_session_ids`
- `query`
- `user_id`
- `limit_per_root`

### 执行流程

1. 根据 `root_session_id` 找到该逻辑会话的所有物理 session
2. 从这些 session 的 `messages` 中检索原始命中片段
3. 对命中的 message 提取：
   - `session_id`
   - `message_id`
   - `sequence_no`
   - `role`
   - `snippet`
   - `score`

### 输出结构

建议：

```json
{
  "root_session_id": 1001,
  "matched_spans": [
    {
      "session_id": 1003,
      "message_id": 88321,
      "sequence_no": 57,
      "role": "assistant",
      "snippet": "删除旧的 docker network app_net 后，重新执行 compose 即可恢复。",
      "score": 0.93
    },
    {
      "session_id": 1002,
      "message_id": 88110,
      "sequence_no": 41,
      "role": "tool",
      "snippet": "ERROR: network app_net already exists",
      "score": 0.88
    }
  ]
}
```

## focused recall summary 设计

### 是什么

focused recall summary 指：

- 围绕当前 query
- 对某个逻辑会话下相关历史内容
- 做一段定向回顾摘要

它不是：

- 整个逻辑会话的大而全总结
- 也不是 compression summary

它回答的是：

- “这条逻辑会话里，和当前 query 最相关的历史是什么”

### 输入数据

推荐输入：

- `query`
- root session 的 title / started_at / last_active_at
- 命中的 `session_summary` / `compression_summary`
- 命中的 message spans
- spans 相邻少量上下文

### 输出形式

建议：

- 1 段面向主 agent 的回顾摘要
- 保留必要命令、路径、错误、结论

## 最终返回结构建议

推荐 `ConversationSearchService` 返回：

```json
{
  "query": "docker network conflict",
  "results": [
    {
      "root_session_id": 1001,
      "tip_session_id": 1003,
      "title": "Docker networking fixes",
      "last_active_at": "2026-05-18T10:30:00Z",
      "summary": "此前该逻辑会话中，用户排查了 Docker network 冲突，最终发现 `app_net` 为陈旧网络，需要先删除再重启 compose。",
      "matched_spans": [
        {
          "session_id": 1002,
          "message_id": 88110,
          "sequence_no": 41,
          "role": "tool",
          "snippet": "ERROR: network app_net already exists"
        },
        {
          "session_id": 1003,
          "message_id": 88321,
          "sequence_no": 57,
          "role": "assistant",
          "snippet": "删除旧的 docker network app_net 后，重新执行 compose 即可恢复。"
        }
      ],
      "sources": {
        "matched_summary_types": ["session_summary", "compression_summary"],
        "matched_session_ids": [1001, 1002, 1003]
      }
    }
  ],
  "count": 1
}
```

## 与 `RecallService` 的协作关系

### `ConversationSearchService`

职责：

- 搜历史
- 找候选 root session
- 回捞原始证据
- 产出结构化 recall results

### `RecallService`

职责：

- 判断当前 run 是否需要跨会话召回
- 调用 `ConversationSearchService`
- 对搜索结果进行压缩或筛选
- 决定哪些 recall results 注入当前 prompt

### 分工原则

- `ConversationSearchService` 不负责当前 run prompt 注入
- `RecallService` 不负责直接做底层数据库检索

## 与现有一期文档的关系

本方案与以下文档直接对齐：

- `02-后端最小落地架构.md`
  - `RecallService` 作为内部服务
  - `session` owner 边界不变
- `03-数据库设计草案.md`
  - 使用 `root_session_id`
  - 使用 `session_summaries`
  - 使用 `messages`
- `05-Session模块详细方案.md`
  - continuation lineage
  - root / tip session
  - `session_summaries` owner 边界

## 一期实现建议

### 必做

1. 基于 `session_summaries.summary_text` 的 FTS 候选召回
2. 按 `root_session_id` 聚合候选逻辑会话
3. 候选逻辑会话内的 `messages` FTS 证据回捞
4. 结构化返回 `matched_spans`
5. 生成 focused recall summary

### 可选但推荐

1. `recent mode`
2. 过滤当前 `root_session_id`
3. 简单的结果融合排序

### 不建议一期就做

1. 全量 `messages` 向量化
2. embedding-first 全局 RAG
3. 复杂 rerank pipeline
4. 独立搜索服务拆分

## 二期演进建议

### summary embeddings

二期非常适合引入：

- `session_summary_embeddings`

建议单独建表，而不是把向量直接塞进 `session_summaries` 主表。

建议字段：

- `id`
- `summary_id`
- `root_session_id`
- `embedding_model`
- `vector`
- `created_at`

### 检索策略升级

二期推荐升级为：

- summary 向量召回
- summary FTS 召回
- 融合排序
- message-level evidence drilldown

也就是说，二期最终推荐形态是：

- **summary-vector candidate recall + summary FTS + message evidence drilldown**

## 最终结论

EchoMind 的 `ConversationSearchService` 最适合采用的形式不是：

- 只用 Hermes 的全库 message-first 搜索
- 也不是只用 `session_summaries` 做简单关键词匹配
- 更不是只靠向量库做黑盒语义召回

而是：

- 用 `session_summaries` 做第一层候选召回
- 按 `root_session_id` 聚合逻辑会话
- 再在候选逻辑会话下回捞 `messages` 里的原始 evidence spans
- 最后生成 focused recall summary

这套方案既继承了 Hermes 的历史追溯思路，又最大化发挥了 EchoMind 当前：

- continuation session
- root session 聚合
- compression summary
- session_summaries 中间真源

这些设计的价值。
