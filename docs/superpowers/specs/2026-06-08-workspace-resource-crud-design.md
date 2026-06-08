# Workspace 资源 CRUD 设计

## 1. 目标

在当前已完成的 `Workspace` 独立页面基础上，补齐资源生命周期管理能力，使 `Workspace` 页面不只是浏览器，而是完整的资源入口。

本次要补齐的能力：

- 创建 `workspace`
- 删除 `workspace`
- 在某个 `workspace` 下创建 `project`
- 删除 `project`

同时明确与 `session` 的关系：

- `session` 仍然是协作入口，不是资源真源。
- 删除 `project` 时，级联删除绑定到该 `project` 的全部 `session`。
- 删除 `workspace` 时，级联删除该 `workspace` 下全部 `project`，并删除这些 `project` 相关的全部 `session`。

## 2. 统一资源模型

本次设计不再保留“本地/远端两套心智”，统一成“可连接环境 + 项目地址”。

### 2.1 Workspace

`workspace` 表示一个可连接的执行环境或机器。

第一版核心字段：

- `id`
- `name`
- `endpoint`
- `created_at`

说明：

- 本地和远端不是两种不同的数据模型。
- 是否本地、是否远端，由 `endpoint` 指向的环境决定，而不是单独依赖 `type` 或 `is_remote` 字段。
- 未来如果需要扩展连接凭据、认证方式、额外配置，可通过扩展配置字段承载，但不影响本次主模型。
- 当前 MVP 阶段只支持本地 workspace。`endpoint` 先作为本地环境标识字段使用，推荐填写 `localhost`。

### 2.2 Project

`project` 表示某个 `workspace` 环境里的具体项目入口。

第一版核心字段：

- `id`
- `workspace_id`
- `name`
- `path`
- `created_at`

说明：

- `project.path` 是统一字段。
- 不再区分 `local_path` / `remote_path`。
- 真正的访问定位统一为：`workspace.endpoint + project.path`。
- 但在当前 MVP 中，文件树与文件内容仍由 gateway 所在机器直接读取本地文件系统，尚未启用远端 endpoint 的真实执行链路。

### 2.3 Session

`session` 仍然保留：

- `workspace_id`
- `project_workspace_id`

原因不是为了维持旧模型，而是因为 `session` 仍然需要明确绑定到当前协作资源。

## 3. 范围

本次在范围内：

- `Workspace` 页面新增 `workspace` 创建与删除
- `Workspace` 页面新增 `project` 创建与删除
- 后端资源模型调整为 `workspace.endpoint` 与 `project.path`
- 删除 `project` 时级联删除 `session`
- 删除 `workspace` 时级联删除 `project + session`
- `Messages` 页面在创建 `session` 时继续选择已有 `workspace + project`
- `Workspace` 页面继续保留只读文件树与文件内容预览

本次不在范围内：

- 文件编辑
- Git 分支或 Proposal 流程改造
- session 页面资源管理能力扩展
- 远端连接协议细分，例如 SSH / HTTP / 容器 / MCP 分类

## 4. 页面交互设计

### 4.1 Workspace 页面整体原则

保留当前你已认可的“代码编译器风格”布局，只在现有语境内增加资源操作。

不新增独立管理页，不把创建和删除操作拆到别的路由。

### 4.2 新建 Workspace

入口位置：

- 左侧 `workspace` 资源导航顶部主按钮

交互形式：

- 打开轻量弹层或侧滑表单

第一版表单字段：

- `Workspace 名称`
- `Endpoint`

行为：

- 创建成功后刷新 `workspace` 列表
- 自动选中新建的 `workspace`
- 自动进入该 `workspace` 视图

### 4.3 删除 Workspace

入口位置：

- `workspace` 节点级操作按钮，建议 hover 显示或更多菜单触发

确认文案必须明确：

- 删除该 `workspace`
- 删除其下所有 `project`
- 删除所有相关 `session`

行为：

- 删除成功后刷新 `workspace` 列表和 `projectsByWorkspace`
- 如果还有其他 `workspace`，自动切到相邻一个或第一个
- 如果已经没有任何 `workspace`，进入空状态页
- 同时清空当前 `project` 选择、文件树和文件内容缓存

### 4.4 新建 Project

入口位置：

- 当前 `workspace` 下的 project 列表头部

交互形式：

- 打开轻量弹层或内联表单

第一版表单字段：

- `Project 名称`
- `Path`

行为：

- 创建成功后刷新当前 `workspace` 下的 project 列表
- 自动选中新建的 `project`
- 自动刷新并展示其文件树区域

### 4.5 删除 Project

入口位置：

- `project` 行级操作按钮

确认文案必须明确：

- 删除该 `project`
- 删除所有绑定到该 `project` 的 `session`
- 不影响同 `workspace` 下其他 `project`

行为：

- 删除成功后刷新当前 `workspace` 下的 project 列表
- 如果还有其他 `project`，自动选到相邻一个或第一个
- 如果已经没有 `project`，回到当前 `workspace` 的空 project 状态
- 清除被删 `project` 的文件树缓存和文件内容缓存

## 5. 后端模型调整

### 5.1 Workspace 模型

从现有模型中保留：

- `id`
- `name`
- `endpoint`
- `created_at`

从核心 API 契约中移除：

- `is_remote`

如果数据库层暂时仍保留旧列，也不应该继续向前端暴露该字段作为主契约。

### 5.2 Project 模型

统一为：

- `id`
- `workspace_id`
- `name`
- `path`
- `created_at`

从核心 API 契约中移除：

- `local_path`
- `remote_path`

### 5.3 Session 级联规则

需要在后端实现，而不是交给前端拼多次删除。

- 删除 `project` 时，先删除关联 `session`，再删除 `project`
- 删除 `workspace` 时，删除其下 `project`，并删除这些 `project` 关联 `session`

原则：

- 删除行为以单个后端接口完成
- 保证结果一致，避免前端串联请求失败时留下脏数据

## 6. API 设计

### 6.1 Workspace

- `POST /api/workspaces`
  - 入参：
    - `name`
    - `endpoint`
- `GET /api/workspaces`
  - 返回 workspace 列表
- `DELETE /api/workspaces/:workspaceId`
  - 删除 workspace，并级联删除其下 project 和 session

### 6.2 Project

- `POST /api/workspaces/:workspaceId/projects`
  - 入参：
    - `name`
    - `path`
- `GET /api/workspaces/:workspaceId/projects`
  - 返回该 workspace 下的 project 列表
- `GET /api/projects/:projectId`
  - 返回单个 project 信息
- `DELETE /api/projects/:projectId`
  - 删除 project，并级联删除关联 session

### 6.3 Files

保留当前已接通的只读接口：

- `GET /api/projects/:projectId/files/tree`
- `GET /api/projects/:projectId/files/content?path=...`

### 6.4 Session

保留：

- `POST /api/sessions`
- `GET /api/sessions`
- `DELETE /api/sessions/:sessionId`

`POST /api/sessions` 仍然要求：

- `workspace_id`
- `project_workspace_id`

## 7. 前端状态流设计

### 7.1 Workspace 页面状态

新增操作状态：

- `creatingWorkspace`
- `creatingProject`
- `deletingWorkspaceId`
- `deletingProjectId`

已有资源状态继续承载：

- `workspaces`
- `projectsByWorkspace`
- `selectedWorkspaceId`
- `selectedProjectId`
- `selectedFilePath`
- 文件树缓存
- 文件内容缓存

### 7.2 创建后的状态行为

- 新建 `workspace` 成功后：
  - 刷新 `workspaces`
  - 自动选中新建项
  - 清空旧的 `selectedProjectId` / `selectedFilePath`
- 新建 `project` 成功后：
  - 刷新当前 `workspace` 下 `projects`
  - 自动选中新建项
  - 加载其文件树

### 7.3 删除后的状态行为

- 删除 `project` 成功后：
  - 从当前 `workspace` 的 project 列表移除
  - 重新计算当前选中的 project
  - 清除该 project 文件树缓存
  - 清除相关文件内容缓存
- 删除 `workspace` 成功后：
  - 从 `workspace` 列表移除
  - 重新计算当前选中的 workspace
  - 清除被删 workspace 下所有 project 缓存
  - 清除相关文件树和文件内容缓存

## 8. Messages 页面影响

`Messages` 页面不增加资源 CRUD 能力，但需要消费最新资源状态。

影响点：

- `session` 创建弹层继续从 `workspace/project` 列表加载选项
- 创建表单字段不变：
  - `Session 名称`
  - `Workspace`
  - `Project`
- 如果某个 `project` 或 `workspace` 被删除，其关联 `session` 下次刷新时必须消失
- 如果需要更即时的体验，`Workspace` 页面删除成功后可以顺手触发 `Messages` 页 session 列表刷新；第一版允许通过重新加载保证一致

## 9. 错误处理

### 9.1 创建错误

- 创建 `workspace` 失败时，提示 endpoint 无效或服务不可用
- 创建 `project` 失败时，提示 path 无效、目录不可访问或资源不存在

### 9.2 删除错误

- 删除 `project` 失败时，提示 project 未删除，session 未变更
- 删除 `workspace` 失败时，提示 workspace / project / session 均未变更

### 9.3 空状态

- 无 workspace：展示空资源页
- workspace 下无 project：展示当前 workspace 的空项目状态
- project 无文件：展示空文件树状态

## 10. 测试重点

### 10.1 后端

- 创建 `workspace` 使用统一 `endpoint`
- 创建 `project` 使用统一 `path`
- `DELETE /api/projects/:id` 级联删除关联 `session`
- `DELETE /api/workspaces/:id` 级联删除其下 `project + session`
- 旧字段 `is_remote` / `local_path` / `remote_path` 不再作为 API 主契约输出

### 10.2 前端

- `workspace` 创建成功后自动选中并进入新 workspace
- `project` 创建成功后自动选中新 project
- 删除 `project` 后选中态正确回退
- 删除 `workspace` 后选中态正确回退
- `Messages` 页 session 创建弹层仍能选择 workspace + project
- 删除资源后，session 列表不再引用已删除资源

## 11. 实施建议

建议实现顺序：

1. 后端统一 `workspace/project` 字段契约
2. 后端补 `DELETE /api/projects/:id` 与 `DELETE /api/workspaces/:id` 级联能力
3. 调整前端 `Workspace` 页加载逻辑，接新字段
4. 补 `workspace` 创建弹层
5. 补 `project` 创建弹层
6. 补 `project` 删除操作
7. 补 `workspace` 删除操作
8. 验证 `Messages` 页 session 选择与删除资源后的刷新一致性

## 12. 决策摘要

本次已确认：

- `workspace` 是机器级或环境级容器
- `workspace` 只保留统一 `endpoint`
- `project` 只保留统一 `path`
- 不再用 `type` 区分本地 / 远端 workspace
- 不再用 `local_path` / `remote_path` 区分 project 地址
- 删除 `project` 时级联删除相关 session
- 删除 `workspace` 时级联删除其下 project 和相关 session
- 所有资源 CRUD 都在当前 `Workspace` 页面语境内完成
