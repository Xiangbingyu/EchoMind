# agenthub可以采取的措施（Hermes 视角）

+ 可以借鉴 Hermes 的 **gateway + platform adapter** 思路，把 AgentHub 的聊天入口设计成统一接入层。前端看起来像飞书/微信式聊天，后端其实是同一个 agent runtime 在服务 Web、IM、IDE 等不同入口。
+ 可以借鉴 Hermes 的 **session context prompt**。不仅保存聊天记录，还要把“这是单聊、群聊、thread、谁 @ 了谁、当前会话属于哪个任务组”这类运行时信息显式喂给模型，让模型知道自己所处的协作场景。
+ 可以借鉴 Hermes 的 **skills**，把“做过一次、以后还会反复做”的流程沉淀成技能文档或模板，而不是每次重新写 prompt。对于 AgentHub，这非常适合沉淀：需求拆解、代码评审、Diff 解释、部署检查、日报总结等流程。
+ 可以借鉴 Hermes 的 **memory + USER.md** 思路，但不要照搬文件存储。EchoMind 更适合把用户偏好、项目规则、模块约定放在结构化存储里，再在 run 开始时生成一个稳定快照注入 prompt。
+ 可以借鉴 Hermes 的 **toolset** 思路。不同场景只开放不同工具，比如普通聊天只给轻量工具，开发会话给代码搜索 / Diff / 预览 / 部署工具，群聊中的 reviewer agent 只给只读工具。
+ 可以借鉴 Hermes 的 **delegate_task**，但要理解它本质上是“同步子代理编排”，不是 durable worker。AgentHub 的 Orchestrator 可以先做成：父 agent 拆任务，子 agent 并发执行，最后父 agent 汇总。
+ 可以借鉴 Hermes 的 **parallel work**，但重点不是“同时跑很多 agent”本身，而是任务边界清晰：前端 agent、后端 agent、测试 agent、文档 agent 分别处理自己的文件或交付物。
+ 可以借鉴 Hermes 的 **gateway session cache**。多会话并行时，后端不一定每次都全新创建 agent runtime，而是可以按 conversation/session 粒度复用部分稳定上下文。
+ 可以借鉴 Hermes 的 **cron / background process watcher**。AgentHub 的“一键部署”“网页预览”“长时间构建”都不应该阻塞当前聊天，可以转成后台任务并在会话里回推状态。
+ 可以借鉴 Hermes 的 **session search + query-focused summary**。历史会话检索不要只做数据库全文搜索，而要做“检索命中 -> 定位相关窗口 -> 生成面向当前问题的摘要”。
+ 可以借鉴 Hermes 的 **profile** 概念。对于 AgentHub，可以演化成“个人工作台 / 团队工作台 / 赛题演示环境”三个隔离上下文，避免不同演示或不同项目互相污染。
+ 可以借鉴 Hermes 的 **terminal environments** 抽象。AgentHub 后续如果要支持本地、容器、远程沙箱、云开发环境，可以统一成 execution environment，而不是把部署能力写死在单一执行器里。
+ 可以借鉴 Hermes 的 **技能市场 / 插件 / MCP** 生态观念。赛题里强调统一适配器层，Hermes 的思路说明：工具与平台接入最好是可插拔的，不要把所有集成写死在主链路。

# 心得

## 1. Hermes 的核心不是“很多 agent 自治”，而是“单主循环 + 外围增强”

Hermes 从产品表面看起来能力很多：CLI、消息平台、技能、记忆、网关、子代理、定时任务、插件、MCP、长任务通知。但从架构上看，它最核心的东西其实很朴素：

1. 每次用户发来一条消息，启动一轮 turn-based agent loop。
2. 这轮 loop 内部完成：组装 prompt、读取长期上下文、调用模型、执行工具、写回结果。
3. 其他所有能力，本质上都是围绕这条主循环服务。

这点对 AgentHub 很关键。赛题虽然强调多 Agent 协作，但一开始不应该把系统做成“很多常驻自治 agent 到处乱跑”。更合理的方式是：

+ 先把单次对话 turn 跑顺。
+ 再把多会话、多 agent、群聊协作、部署、预览这些能力接在主循环外围。

也就是说，**Hermes 给我们的最大启发，不是功能清单，而是复杂度控制方式。**

## 2. Hermes 为什么很适合拿来对照 AgentHub 赛题

赛题要求的重点有几个：

1. IM 聊天式自然交互
2. 单聊、多会话并行
3. 通过 `@` 指令实现群聊协作
4. Orchestrator 任务拆解
5. 代码 Diff、网页预览、一键部署
6. 统一适配器层
7. 强调 Prompt 工程与架构创新

Hermes 虽然不是专门为这个赛题设计的，但它恰好踩中了很多底层共性问题：

+ 它本身就有 gateway，说明“同一个 agent runtime 适配多个聊天入口”是成立的。
+ 它本身就有 delegation，说明“父 agent 拆任务，子 agent 并发处理”是成立的。
+ 它本身就有技能、记忆、会话搜索、上下文压缩，说明“如何把长对话和长期协作做稳定”这件事是必须认真设计的。
+ 它本身就有 toolsets、profiles、插件、MCP，说明“统一适配器层”和“按场景裁剪能力边界”不是锦上添花，而是系统可控性的前提。

换句话说，Claude Code 更像“开发代理体验的样板”，而 Hermes 更像“多入口、多能力、可扩展 agent 基础设施的样板”。

## 3. Hermes 最值得 AgentHub 学的几个点

## 3.1 Gateway 不是附属功能，而是产品主入口

Hermes 的 gateway 不是简单地把消息转发给模型，而是承担了很多运行时职责：

+ 识别消息来自哪个平台、哪个用户、哪个会话。
+ 维护会话级 agent runtime 和会话缓存。
+ 处理 stop / resume / slash command / background notification。
+ 给模型补充平台上下文和会话上下文。

这对 AgentHub 的启发是：

+ Web 聊天界面、移动端 IM 风格界面、IDE 插件，不应该分别写三套“聊天逻辑”。
+ 真正需要统一的是：`message -> session -> runtime -> tool execution -> response delivery` 这条链路。
+ 前端只是不同皮肤，真正的业务骨架在统一接入层和统一 agent runtime。

如果 AgentHub 想实现“像微信/飞书一样自然”，核心不只是 UI 像不像，而是后端是否真正理解：

+ 当前消息属于哪个会话
+ 当前是私聊还是群聊
+ 当前群里有哪些 agent
+ 当前是不是由某个用户通过 `@agent` 显式触发
+ 当前这个 agent 回答后，是否还需要继续交给 Orchestrator 或其他 agent

## 3.2 Session 不只是消息表，而是协作上下文的载体

Hermes 的一个重要设计点，是它会构造 session context prompt，把平台、会话来源、共享关系等信息告诉模型。

这个思路非常适合 AgentHub，因为赛题里的协作不是普通问答，而是带明显结构的：

+ 单聊：用户和某个 agent 单独推进任务
+ 多会话并行：同一个项目下有多个 topic / thread 同时推进
+ 群聊协作：用户 `@产品agent`、`@前端agent`、`@测试agent` 进行角色协作

如果没有 session context，模型看到的只是“消息文本”；有了 session context，模型看到的是“这条消息在什么协作语境下出现”。

所以 AgentHub 可以考虑把 session 层拆成两部分：

1. **消息真源**
   - 用户消息
   - agent 回复
   - 工具结果
   - Diff / 预览 / 部署状态

2. **会话上下文视图**
   - 会话类型：单聊 / 群聊 / thread
   - 参与者：用户、agent、Orchestrator
   - 当前任务主题
   - 当前协作状态：需求澄清 / 开发中 / 测试中 / 等待部署
   - 是否由 `@` 指令触发

## 3.3 Skills 比“写 prompt”更接近真正的产品积累

Hermes 很强调 skills。它的逻辑不是“每次都写更聪明的提示词”，而是把成功做过的流程变成可复用技能。

这非常适合赛题，因为老师和评委真正想看到的，不只是你能把一个问题答出来，而是你能不能把协作经验沉淀下来。

AgentHub 可以沉淀的技能至少包括：

+ 需求澄清 skill：把用户自然语言整理成需求文档
+ 拆任务 skill：把需求拆成前端、后端、测试、部署四类任务
+ Diff 讲解 skill：把代码修改总结成非技术人员也能看懂的说明
+ 预览验收 skill：检查页面是否能打开、关键交互是否正常
+ 部署前检查 skill：环境变量、构建命令、健康检查
+ 发布总结 skill：输出发布说明、风险点、回滚建议

这类能力一旦做成 skill，就会从“某次演示比较聪明”变成“系统真的可复用、可迭代”。

## 3.4 Memory / User Profile 要和 Session History 分层

Hermes 里有 `MEMORY.md` 和 `USER.md`，本质上对应：

+ 长期记忆
+ 用户画像 / 用户偏好

同时它还有 session persistence 和 session search。也就是说，它没有把所有上下文都塞进同一个桶里。

AgentHub 也应该明确区分至少三类东西：

1. **session history**
   - 当前会话发生过什么
   - 适合短中期任务推进

2. **memory**
   - 项目长期约定
   - 常见坑
   - 技术偏好
   - 反复出现的事实

3. **profile**
   - 这个用户喜欢怎么沟通
   - 喜欢先看结论还是先看分析
   - 更偏产品表达还是技术表达

Hermes 还给了一个很重要的工程启发：**当前 run 用的是快照，不是数据库实时值。**

也就是说：

+ run 开始时装配一次稳定 prompt
+ 中途 memory/profile 即使被更新，也不强制改写当前 run 的稳定前缀
+ 新快照在下一个 run 再生效

这有利于保持 prompt 稳定、缓存稳定、行为稳定。

## 3.5 Delegation 很适合做 Orchestrator，但不要误解成“后台常驻多 agent”

Hermes 的 `delegate_task` 非常值得研究，但也很容易被误读。

它的真实含义更接近：

+ 父 agent 发起一个子任务
+ 子 agent 在隔离上下文里完成工作
+ 父 agent 阻塞等待子 agent 返回总结
+ 如果父 agent 被中断，子 agent 也会被取消

这说明它本质上是：

+ **同步子代理编排**

而不是：

+ **长期独立运行的后台自治体**

这个差别很重要。对于 AgentHub 的 Orchestrator，第一版其实就应该做成前者：

1. 用户在群里提出目标
2. Orchestrator 判断要不要拆任务
3. 按角色启动若干子 agent
4. 子 agent 只返回摘要、Diff、状态、建议
5. Orchestrator 汇总后回到主会话

这样做有几个好处：

+ 容易演示
+ 易于控制成本
+ 任务边界清晰
+ 不容易产生“后台 agent 跑飞了”的失控问题

## 3.6 Toolset 思维比“工具越多越好”更重要

Hermes 的工具系统不是简单堆工具，而是通过 toolset 控制“谁在什么场景能用什么”。

这个思想对于 AgentHub 非常关键，因为赛题里天然有多种角色：

+ 产品 agent
+ 前端 agent
+ 后端 agent
+ 测试 agent
+ 部署 agent
+ Orchestrator

这些角色不应该共享完全相同的工具权限。

一个更合理的做法是：

+ 产品 agent：文档、需求整理、网页搜索、只读代码浏览
+ 前端 agent：文件编辑、预览、浏览器检查、前端构建
+ 后端 agent：后端代码、终端、接口调试、测试
+ 测试 agent：测试执行、日志读取、Diff 分析
+ 部署 agent：构建、部署、环境检查、回滚脚本
+ Orchestrator：任务拆分、状态汇总、消息协调，少量只读工具

这样一来，系统看起来更像一个真正的团队，而不是多个“拥有无限权限的同质 agent”。

## 3.7 Background Process / Cron 很适合承接“预览”和“部署”

Hermes 对长任务的处理方式也值得借鉴：

+ 长时间运行命令可以后台执行
+ 运行结束后，通过 watcher 把结果通知当前会话
+ cron 则负责周期性任务

AgentHub 很需要这类能力，因为：

+ 网页预览不是瞬时完成的
+ 构建和部署不是瞬时完成的
+ 自动巡检、日报、回归测试也不是瞬时完成的

因此，AgentHub 不应把“部署”“预览”“构建”强行塞进一次同步 turn 里。更好的设计是：

+ 主会话里触发任务
+ 任务转为后台 job
+ 会话收到实时状态回推
+ 任务完成后生成一个新的 agent turn 做结果解释

这比“用户一直盯着一个回答等 2 分钟”更像 IM 产品。

## 3.8 Session Search 的价值不只是检索，而是“带问题去回忆”

Hermes 的 session_search 很值得借鉴的一点是：它不是简单返回一堆命中文本，而是围绕当前 query 做聚合和摘要。

这对 AgentHub 非常重要，因为多会话并行后，真正的问题不再是“有没有历史”，而是：

+ 当前这条消息和哪段历史最相关
+ 这些历史里哪些内容值得重新带回上下文
+ 应该返回原文，还是返回针对当前任务的总结

所以 AgentHub 的 recall 更像一个管道：

1. 从历史消息 / 摘要 / 文档中检索候选
2. 选出与当前任务最相关的窗口
3. 压缩成 query-focused summary
4. 注入当前 run

## 4. Hermes 对 AgentHub 赛题的直接映射

## 4.1 IM 聊天式交互

Hermes 证明了：消息平台不是只能做“机器人问答”，也可以承载完整工具调用、长期会话、权限控制和后台通知。

对 AgentHub 来说，重点不是做一个“大模型网页壳”，而是做一个真正的会话系统：

+ 消息是第一入口
+ 任务状态通过消息推进
+ 预览 / 部署 / Diff / 汇总都回到消息流里

## 4.2 单聊与多会话并行

Hermes 的 session persistence、profile、session search 都说明：多会话并行不是前端 tab 功能，而是后端运行时与存储设计问题。

AgentHub 应至少支持：

+ 每个项目多个会话
+ 每个会话有独立上下文
+ 会话之间允许检索和引用
+ 同一用户在不同会话里可以并行派发任务

## 4.3 `@` 群聊协作

Hermes 原生更偏“单 agent 对多入口”，但它的 gateway、session context、delegation 已经提供了足够多的借鉴。

AgentHub 可以在这之上向前走一步：

+ `@前端agent`：把消息路由给前端 agent
+ `@后端agent`：把消息路由给后端 agent
+ `@orchestrator`：让协调器来拆解和调度
+ 未显式 `@` 时，由默认 agent 或系统路由规则处理

这本质上是“消息路由 + agent runtime 选择 + session context 注入”的问题。

## 4.4 Orchestrator 任务拆解

Hermes 的 delegation 说明第一版可以很务实：

+ 不用一开始就做复杂的 DAG 调度系统
+ 先做同步 fan-out / fan-in
+ 父 agent 负责拆解、汇总、裁决
+ 子 agent 负责局部执行

如果演示效果需要更强，再往后增加：

+ 任务状态看板
+ durable task queue
+ 跨 agent 交付物协议
+ 失败重试和补偿

## 4.5 Diff、预览、一键部署

Hermes 的 tool system、background watcher、gateway 回推，说明这三类功能完全可以统一到同一条产品链路中：

+ Diff：作为工具结果或回复附件返回
+ 预览：作为后台任务启动并回传 URL 与验收状态
+ 部署：作为后台流水线执行，并在会话里持续播报状态

这和传统 DevOps 平台不同，它更强调“结果回到聊天上下文”。

## 4.6 Prompt 工程与架构选型

Hermes 很大的价值在于提醒我们：

+ Prompt 工程不只是写系统提示词
+ 更重要的是如何组织长期上下文、技能、记忆、会话历史、平台信息、工具能力

真正拉开差距的不是某一句 prompt 写得多花，而是：

+ stable prefix 怎么设计
+ dynamic context 怎么召回
+ role toolset 怎么裁剪
+ 任务拆解怎么组织
+ 后台任务怎么回流到会话

这其实就是架构问题，不只是 prompt 问题。

## 5. 我觉得最适合 AgentHub 的落地方向

如果只基于赛题做一个“够强、够清晰、好演示”的版本，我会建议按下面的优先级落地：

### 第一层：必须做稳

+ 统一消息入口
+ 单 agent 主循环
+ session 持久化
+ 工具注册与权限控制
+ Diff / 预览 / 部署三条工具链
+ 多会话并行

### 第二层：体现亮点

+ `@agent` 群聊协作
+ Orchestrator 同步拆任务
+ skill 化的协作模板
+ 面向当前任务的历史召回
+ 后台任务结果回推

### 第三层：作为创新分

+ profile / team profile
+ 多环境执行器
+ 插件或 MCP 扩展
+ 定时任务 / 自动日报
+ 可视化任务看板

## 6. 不建议直接照搬 Hermes 的地方

Hermes 很强，但并不意味着它的一切都适合 EchoMind / AgentHub。

我觉得至少有几件事不要直接照搬：

+ **不要照搬文件型 memory 真源。** Hermes 的 `MEMORY.md / USER.md` 很适合本地 agent 产品，但 EchoMind 更适合结构化存储。
+ **不要把多 agent 理解成长期自治进程。** 比赛版本更需要可控、清晰、可演示，而不是复杂自治。
+ **不要一开始就背上完整插件生态。** MCP / plugin 可以预留接口，但第一版不必全部做满。
+ **不要把 gateway 当成“适配层小功能”。** 它其实应该是主架构层。
+ **不要只卷 prompt。** 如果 session、toolset、orchestrator、后台任务没有设计好，再好的 prompt 也顶不住复杂协作场景。

## 7. 一句话总结

Hermes 最值得 AgentHub 学的，不是某个孤立功能，而是它把 **聊天入口、会话状态、长期记忆、技能沉淀、工具边界、子代理拆解、后台任务** 组织成了一套比较清晰的 agent 基础设施。

如果 Claude Code 更像“怎么把开发代理做得顺手”，那 Hermes 更像“怎么把一个可扩展、可多入口、可长期协作的 agent 系统搭起来”。  
对 AgentHub 这道赛题来说，后者其实更接近我们真正需要解决的问题。

## 参考

+ `docs/调研/hermes-agent-src/README.zh-CN.md`
+ `docs/调研/hermes-agent-src/AGENTS.md`
+ `docs/调研/hermes-agent-src/website/docs/developer-guide/architecture.md`
+ `docs/调研/hermes-agent-src/website/docs/guides/delegation-patterns.md`
+ `docs/调研/Hermes-Agent-架构借鉴分析.md`
+ `docs/调研/Hermes-Agent-设计总结-分享版.md`
