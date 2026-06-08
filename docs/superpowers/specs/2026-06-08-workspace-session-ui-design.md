# Workspace 与 Session UI 改造设计

## 1. 目标

本次改造要解决两个当前被混在一起的问题：

- `workspace` 资源管理缺少独立入口与独立页面。
- `session` 的创建与删除缺少与 `workspace` / `project workspace` 的明确绑定流程。

改造后的边界如下：

- `workspace` 是纯资源容器，只负责资源管理，不反向关联任何 `session`。
- `project workspace` 是 `workspace` 下的项目级工作区，是文件树与文件预览的承载对象。
- `session` 是协作入口，创建时必须绑定一个 `workspace` 和一个 `project workspace`。
- `session` 可以向其绑定的 workspace 体系写入内容和运行态产出，但 `workspace` 页面不承载 session 管理。

## 2. 范围

本次在范围内：

- 左侧导航新增 `Workspace` 入口。
- 新增独立 `Workspace` 页面。
- `Workspace` 页面支持查看与创建 `workspace`。
- `Workspace` 页面支持进入单个 `workspace` 查看其下 `project workspace`。
- `Workspace` 页面支持按 GitHub 风格进行只读文件浏览。
- `Messages` 页面新增 `新建 Session` 按钮。
- `Messages` 页面支持删除 `session`。
- `session` 创建时必须选择已有的 `workspace` 和 `project workspace`。

本次不在范围内：

- 在 `session` 创建弹层里新建 `workspace` 或 `project workspace`。
- 在 `Workspace` 页面展示或管理 `session`。
- 文件编辑、重命名、删除、新建目录、新建文件。
- Git 分支、提交状态、差异浏览、代码变更操作。
- `workspace` 删除与联动清理策略。

## 3. 现状与问题

当前前端只有 `Messages` 页面和一个右侧 `WorkspacePanel`。

- `Messages` 页面同时承担聊天、会话切换、运行态显示和部分 workspace 快照展示。
- 右侧 `WorkspacePanel` 展示的是当前 session 的运行态快照，不是资源管理页面。
- 左侧导航目前只有 `Messages` 入口，没有独立的 `Workspace` 管理页。
- 当前 `session` 列表只有选择能力，没有正式的新建/删除交互。

这导致两个问题：

- `workspace` 资源管理和 `session` 聊天协作被混在一个页面语义里。
- 后续如果继续扩展 workspace、project workspace、文件浏览，会直接挤压消息页布局并放大状态耦合。

## 4. 信息架构

页面职责拆分如下：

- `Messages` 页面
  - 负责会话列表。
  - 负责消息加载、消息发送、流式输出、session 创建、session 删除。
  - 负责显示当前 session 的运行态信息。
- `Workspace` 页面
  - 负责 workspace 列表与 workspace 创建。
  - 负责单个 workspace 详情浏览。
  - 负责 project workspace 列表与只读文件浏览。
- 侧边导航
  - 作为一级入口，至少包含 `Messages` 和 `Workspace`。

关键约束：

- `workspace` 页面不显示 session。
- `workspace` 不反向挂 session。
- `session` 创建时强绑定 `workspace` 和 `project workspace`。
- 运行态侧栏不再承担资源管理角色。

## 5. 页面设计

### 5.1 左侧导航

左侧导航新增 `Workspace` 入口，与现有 `Messages` 平级。

导航层只负责页面切换，不在导航层承载 workspace 卡片或 session 选择。

### 5.2 Workspace 首页

点击 `Workspace` 入口后进入独立管理页。

页面结构：

- 顶部页头
  - 页面标题 `Workspace`
  - 搜索输入位
  - `新建 Workspace` 按钮
- 主内容区
  - `workspace` 卡片网格

每张 workspace 卡片至少包含：

- 名称
- 简短描述或占位文案
- `project workspace` 数量
- 最近更新时间

交互规则：

- 点击卡片进入该 `workspace` 详情页。
- 如果没有数据，展示空状态并引导创建第一个 workspace。

### 5.3 Workspace 详情页

进入单个 workspace 后，展示该 workspace 下的 `project workspace` 列表。

页面结构：

- 顶部面包屑或返回按钮
  - 返回 `Workspace` 首页
- 顶部信息区
  - workspace 名称
  - 简介或说明
  - 基础统计信息
- 主内容区
  - `project workspace` 列表

`project workspace` 的第一版展示形式建议为列表卡片或 GitHub 风格仓库行视图。每项至少包含：

- 名称
- 本地路径或路径摘要
- 最近更新时间
- 可选的轻量预览入口

关于“预览文件”的第一版约束：

- 不在 workspace 首页卡片层直接展示完整文件树。
- 在 `project workspace` 列表层允许轻量展开预览，内容只到顶层目录或少量文件摘要。
- 完整文件浏览进入 `project workspace` 详情视图后展示。

### 5.4 Project Workspace 文件浏览视图

文件浏览视图采用 GitHub 风格的只读浏览体验。

页面结构：

- 顶部面包屑
  - `Workspace 首页 / 当前 Workspace / 当前 Project Workspace`
- 左侧目录区
  - 目录树或当前目录列表
- 右侧内容区
  - 文件内容预览

第一版能力：

- 浏览目录
- 点击文件查看内容
- 切换文件内容预览

第一版不做：

- 在线编辑
- 文件上传
- 新建 / 删除 / 重命名
- Git 变更状态
- 分支切换

## 6. Messages 页面改造

### 6.1 Session 列表

`Messages` 页面继续作为聊天协作页存在，保留：

- session 列表
- 聊天主区
- 当前 session 的运行态信息区

### 6.2 新建 Session

在 session 列表头部新增 `新建 Session` 按钮。

点击后打开创建栏或弹层。第一版表单字段最小化为：

- `Session 名称`
- `Workspace`
- `Project Workspace`

交互规则：

- 用户必须先选 `Workspace`。
- `Project Workspace` 选项根据当前 `Workspace` 过滤。
- 只有字段有效时才允许提交。
- 如果没有可选 `workspace` 或没有可选 `project workspace`，只提示去 `Workspace` 页面先创建资源，不在当前弹层内补建。

创建成功后：

- 新 session 立即出现在会话列表中。
- 自动选中新 session。
- 聊天主区自动切换到该 session。

### 6.3 删除 Session

删除入口位于 session 列表项操作区，建议采用悬停按钮或更多菜单。

删除规则：

- 删除只作用于 session 及其消息历史。
- 删除不影响任何 `workspace` 或 `project workspace`。
- 执行删除前需要二次确认。

删除成功后的列表行为：

- 如果删除的是当前选中 session，且列表中还有其他 session，则自动切换到相邻一个 session。
- 如果删除后已经没有 session，则聊天主区回到空状态。

## 7. 运行态面板调整

当前右侧 `WorkspacePanel` 展示的是当前 session 的运行态快照，包括：

- 当前 session 基础信息
- workspace snapshot
- runtime 状态
- tree / plan / sandbox / agent 状态

这类信息仍然属于 `Messages` 页面上下文，但名称和语义需要收敛，避免和新的 `Workspace` 页面冲突。

建议调整为：

- 保留该面板在 `Messages` 页面中的存在。
- 将其语义定位为 `Runtime` 或 `Session Context`。
- 继续承载当前 session 绑定运行态的实时信息。
- 不再将其视为资源管理页，也不承担 workspace 创建、选择或浏览职责。

## 8. 前端状态拆分

前端状态应按页面职责拆分为两组。

### 8.1 Session 状态

仅服务 `Messages` 页面：

- session 列表
- 当前选中 session
- 当前 session 消息
- 流式发送状态
- 新建 / 删除 session 状态
- 当前 session 的运行态信息

### 8.2 Workspace 状态

仅服务 `Workspace` 页面：

- workspace 列表
- workspace 创建状态
- 当前选中的 workspace
- 当前 workspace 下的 project workspace 列表
- 当前 project workspace 文件树
- 当前打开文件路径
- 当前文件内容预览

拆分原则：

- 不要继续在 `Messages` 页面里维护资源管理页状态。
- 不要让 `Workspace` 页面依赖当前活动 session 才能工作。

## 9. 接口契约

第一版至少需要以下接口能力。

### 9.1 Workspace 相关

- `GET /api/workspaces`
  - 返回 workspace 列表。
- `POST /api/workspaces`
  - 创建 workspace。
- `GET /api/workspaces/:workspaceId/project-workspaces`
  - 返回某个 workspace 下的 project workspace 列表。

### 9.2 Project Workspace 文件浏览相关

- `GET /api/project-workspaces/:projectWorkspaceId/tree`
  - 返回目录树或目录列表。
- `GET /api/project-workspaces/:projectWorkspaceId/file?path=...`
  - 返回指定文件内容。

### 9.3 Session 相关

- `POST /api/sessions`
  - 创建 session。
  - 请求体必须包含 `workspace_id` 和 `project_workspace_id`。
- `DELETE /api/sessions/:sessionId`
  - 删除指定 session。

如果后端暂时缺少完整实现，也应先统一接口字段契约，避免前端将假数据结构写死。

## 10. 错误处理与空状态

需要明确处理以下场景：

- workspace 列表为空
- 某个 workspace 下没有 project workspace
- 文件树为空或读取失败
- 文件内容过大或读取失败
- 创建 session 时缺少可选资源
- 删除 session 失败

交互原则：

- 对资源缺失优先给出明确引导，而不是静默失败。
- 创建 session 的失败提示要指出缺的是 `workspace` 还是 `project workspace`。
- 删除 session 的提示文案必须明确“不影响 workspace 资源”。

## 11. 测试重点

前端改造后至少验证以下行为：

- 左侧导航可在 `Messages` 与 `Workspace` 之间正确切换。
- `Workspace` 首页可加载、搜索、展示卡片与空状态。
- 创建 workspace 后，workspace 卡片列表正确刷新。
- 进入 workspace 后，project workspace 列表正确显示。
- 打开 project workspace 后，目录树和文件预览正确工作。
- `Messages` 页面可打开新建 session 弹层。
- 选择 workspace 后，project workspace 下拉项正确联动过滤。
- 创建 session 成功后自动选中并进入聊天页。
- 删除当前 session 后列表与主区切换逻辑正确。
- 删除 session 不影响 workspace 页面资源展示。
- `Messages` 页右侧运行态面板仍能展示当前 session 运行态。

## 12. 分步实施建议

建议按以下顺序实施：

1. 新增左侧导航 `Workspace` 入口与独立路由。
2. 搭建 `Workspace` 首页与 workspace 卡片网格。
3. 接入 workspace 创建能力。
4. 搭建 workspace 详情页与 project workspace 列表。
5. 接入 project workspace 文件树与文件内容只读预览。
6. 改造 `Messages` 页面，新增 session 创建弹层。
7. 接入 session 删除能力。
8. 收敛现有右侧 `WorkspacePanel` 的命名与语义，使其变成 session 运行态面板。

这个顺序可以保证：

- 聊天主流程不需要先被大改。
- 资源管理页可以独立推进。
- session 创建逻辑在资源入口稳定后再接入，避免界面先行但数据源不稳。

## 13. 决策摘要

本次设计已确认以下关键决策：

- `workspace` 与 `project workspace` 是两层真实独立实体。
- `workspace` 只通过 `Workspace` 页面管理。
- 删除 session 只删除 session 与消息历史，不删除任何 workspace 资源。
- session 创建弹层只能选择已有 `workspace` 和已有 `project workspace`。
- `Workspace` 页面采用独立管理页模式，不嵌入 `Messages` 页面。
- workspace 首页展示卡片网格。
- 进入 workspace 后展示 project workspace 列表。
- 文件浏览第一版只做目录树 + 文件内容只读预览。
- workspace 页面不显示 session，只有 session 绑定 workspace。
