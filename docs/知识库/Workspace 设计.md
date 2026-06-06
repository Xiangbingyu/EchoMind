# AgentHub Workspace 方案
这套方案的核心目标，是把“聊天负责沟通，Workspace 负责落地”明确拆开。聊天默认只是协作入口， 只有挂载了 Workspace，Agent 才能进入代码协作态，并围绕项目、Proposal、Sandbox 和版本记录展开稳定协作。 

<font style="background-color:rgba(255, 255, 255, 0.14);">手动创建 Workspace</font><font style="background-color:rgba(255, 255, 255, 0.14);">聊天需挂载后才能代码协作</font><font style="background-color:rgba(255, 255, 255, 0.14);">Proposal Branch 驱动合并</font><font style="background-color:rgba(255, 255, 255, 0.14);">Sandbox 基于基础镜像启动</font><font style="background-color:rgba(255, 255, 255, 0.14);">支持个人与群聊共创</font><font style="background-color:rgba(255, 255, 255, 0.14);">切换 Workspace 会清空当前执行态上下文</font><font style="background-color:rgba(255, 255, 255, 0.14);">Confirm、Push、Deploy 三阶段分离</font>

## 一、整体分层
顶层增加一个 Workspace 总层，下面保留现有五层结构。Workspace 不是账号天然唯一绑定的默认空间，而是由用户按需创建。 

**1. Workspace**用户手动创建的顶层协作空间，可用于个人开发或多人共创，是项目、Proposal、版本与执行上下文的持久化边界。

**2. Project Workspace**Workspace 下某个项目的持久化工作区，用于承载源码、配置、项目级 Proposal 与版本历史；在接入 Git 后，这一层底层绑定一个 Git Repository。

**3. Proposal Pool**项目级待确认变更池，用于汇总多个 Agent 在 Sandbox 中产出的 Diff、测试结果、预览链接与风险说明；在接入 Git 后，可映射为一组待确认的 Proposal Branch。

**4. Agent Sandbox**某个 Agent 在某次会话或任务中的临时执行环境，基于 Project Workspace 快照创建，用于编码、测试、构建与预览；在 Git 模式下，本质上是基于基线提交 checkout 出来的工作副本。平台在云端维护默认基础镜像，至少包含 git、基础 shell 与常用工具；每次创建 Sandbox 时，都基于该镜像拉起临时环境，可从缓存恢复，也可重新构建，任务结束后自动销毁。

**5. Execution Environment**对本地、容器、远程沙箱、云开发环境等执行载体的统一抽象，用于承载 Sandbox 运行。当 Sandbox 需要运行测试、构建或预览时，Execution Environment 应根据项目配置进一步准备依赖环境，必要时直接切换到 Docker 或容器化执行模式。

**6. Version History**Proposal 被确认并应用后形成的项目级版本记录，用于回看、对比、审计与回滚；在 Git 模式下，可直接映射为 commit、merge 和 tag 历史。

## 二、核心设计原则
这套方案试图解决“聊天上下文”“代码落地”“多人协作”“Agent 并行执行”之间容易混淆的问题。

沟通与落地分离

### 聊天不是代码真源
聊天负责讨论、拆解、汇报；Workspace 和 Project Workspace 才是真正承接代码、文件与版本的持久化边界。

执行与持久化分离

### Sandbox 不直接落盘
Agent 先在临时 Sandbox 内工作，结果以 Proposal 的形式进入确认流程，而不是直接覆盖项目真源。

协作与权限分离

### Workspace 不等于全量可见
Agent 默认只应访问当前会话绑定且已授权的 Project Workspace，而不是自动看到所有工作区与项目。

## 三、会话进入代码协作态流程
只有当聊天挂载了 Workspace，Agent 才能开始实际的工程协作。

**创建聊天**

单聊或群聊先作为普通沟通容器存在

→

**挂载 Workspace**

明确当前会话对应的协作空间与落地区域

→

**绑定 Project Workspace**

让 Agent 在具体项目范围内执行任务

→

**创建 Agent Sandbox**

基于基础镜像和项目快照拉起临时环境，进入编码、测试、构建与预览

→

**进入代码协作态**

允许读写文件、提交 Proposal、沉淀版本记录

 设计约束：未挂载 Workspace 的聊天仍然可以用于需求讨论、任务拆解、Diff 解释和结果汇报，但不直接修改项目文件。 

## 四、Proposal 驱动的代码落地流程
Agent 负责产出，Workspace 负责落地，Proposal Pool 负责把两者安全连接起来；在接入 Git 后，这套流程会映射为 branch、merge 与版本沉淀。

**Project Workspace**

作为项目真源，基于当前主线生成快照供 Agent 使用

→

**Agent Sandbox**

Agent 在隔离环境中基于 proposal branch 写代码、跑测试、产出预览；测试前按项目配置补齐依赖环境，必要时进入 Docker 模式

→

**Proposal Pool**

汇总 Proposal Branch 的 Diff、测试结果、风险说明与预览链接

→

**Confirm（Merge）**

用户或 Orchestrator 对 Proposal 审阅后，决定是否合并进项目主线

→

**Version History**

Proposal 合并后更新项目真源，并生成新的项目版本记录

 这样做的好处是：即使多个 Agent 并行工作，也不会直接污染项目真源；所有修改都能被审阅、追踪和回滚，且底层可以自然映射到 Git 分支与合并策略。 

## 五、单聊与群聊绑定方式
同样是聊天入口，单聊和群聊在 Workspace 绑定与权限控制上需要区分处理。

单聊模式

### 个人开发或个人委派
+ 用户先创建或选择一个 Workspace。
+ 单聊挂载该 Workspace 后，Agent 才能进入代码协作态。
+ 用户可基于不同 Workspace 创建不同会话，分别处理不同项目或任务。
+ 已进入开发态的会话，优先新建或派生会话，而不是频繁直接切换 Workspace。

群聊模式

### 多人协作或多 Agent 共创
+ 群聊在进入共创模式前，也必须绑定一个 Workspace。
+ 所有成员和多个 Agent 的产出统一落在该 Workspace 下，避免落到某个成员个人私有空间。
+ Workspace 切换应由管理员执行，第一版可先约定群主默认拥有该权限。
+ Proposal、版本记录与项目文件都以该群聊绑定的 Workspace 为归属边界。

## 六、关键规则总表
把适合产品实现与答辩说明的规则集中整理成表，方便后续直接引用。

| **<font style="color:#1d4ed8;">规则名称</font>** | **<font style="color:#1d4ed8;">规则内容</font>** | **<font style="color:#1d4ed8;">设计目的</font>** |
| --- | --- | --- |
| Workspace 创建规则 | Workspace 不是账号天然唯一绑定，而是由用户按需手动创建。 | 支持一个用户管理多个独立项目域，也支持后续扩展到共享工作区。 |
| 聊天挂载规则 | 聊天只有在挂载 Workspace 后，Agent 才能进入代码协作态。 | 把普通讨论与真实工程修改分开，避免聊天直接污染项目真源。 |
| 会话绑定规则 | 一个会话在任意时刻只应绑定一个 Workspace。 | 保持当前上下文、文件归属和 Proposal 归属清晰一致。 |
| 切换清空规则 | 切换 Workspace 时，应清空当前 Workspace 部分的聊天内容与执行态上下文。 | 避免不同项目之间的上下文串扰和错误继承。 |
| 权限边界规则 | Agent 默认只访问当前会话绑定且已授权的 Project Workspace。 | 确保多项目并存时的权限最小化和信息隔离。 |
| Proposal 提交流程规则 | Agent 不直接写回项目真源，而是先在 Sandbox 中生成 Proposal 再进入确认流程。 | 提升稳定性、可追溯性和多人协作下的并发安全。 |
| Sandbox 运行环境规则 | 平台维护默认基础镜像，Sandbox 基于该镜像创建；测试或构建时再按项目配置补齐依赖环境，必要时进入 Docker 或容器模式；任务结束后自动销毁。 | 保持基础环境一致、减少脏状态积累，并提升测试与构建的可重复性。 |
| Git 嵌入规则 | Git 嵌入在 Project Workspace 层，作为项目真源的底层版本控制引擎。 | 让产品层的项目语义与工程层的版本语义保持清晰映射。 |
| Proposal Branch 规则 | 每个 Proposal 对应一个独立分支，Agent 在自己的 Sandbox 中围绕该分支工作。 | 避免直接污染主分支，并支持多 Agent 并行协作。 |
| Confirm / Push / Deploy 分离规则 | Confirm 表示 merge，push 表示项目主线同步到远端，deploy 表示把稳定版本发布到运行环境。 | 避免把代码确认、远端同步和部署发布混成一个动作。 |
| 版本沉淀规则 | 每次 Proposal 被应用后，都应生成版本记录。 | 支持历史回看、版本对比、审计和必要时回滚。 |


## 七、实现建议
如果这套方案进入产品设计或答辩阶段，可以优先突出下面这些实现要点。

**规则 1：聊天负责沟通，Workspace 负责落地**

把会话系统与工程真源清晰分离，是控制复杂度和减少错误的关键。

**规则 2：Proposal 是唯一正规写回通道**

所有 Agent 修改结果统一进入 Proposal Pool，再由用户或 Orchestrator 确认落盘。

**规则 3：Sandbox 负责执行，Project 负责持久化**

不要让 Agent 直接把试错代码写入真源，避免多人并行时的覆盖与污染。

**规则 3.1：基础镜像与项目依赖环境分层**

平台先维护统一的基础 Sandbox Image，保证每个临时环境至少具备一致的 Git 与基础工具；真正与项目相关的依赖，则在运行测试或构建前按配置动态准备，必要时直接切到 Docker 或容器化执行。

**规则 4：切换 Workspace 等于切换协作语境**

切换不是简单换目录，而是切换会话的项目边界、上下文和权限，因此应清空当前执行态。

**规则 5：Git 只落在项目层，不落在聊天层**

聊天系统只负责沟通和协作入口，Git Repository 应绑定在 Project Workspace 层，避免模型语义和版本语义混乱。

**规则 6：Confirm 不是 Push，Push 不是 Deploy**

Confirm 是代码进入项目真源，Push 是稳定版本同步远端，Deploy 是把选定版本发布到预览、测试或生产环境。

## 八、Git 接入设计
采用方案 A，即每个 Proposal 对应一个独立分支。Git 不取代 Workspace，而是作为 Project Workspace 的底层版本引擎。

Git 嵌入位置

### 嵌入在 Project Workspace 层
一个 Project Workspace 默认绑定一个 Git Repository。Workspace 管协作空间和权限，Project Workspace 管具体项目与 Git 主线。

分支策略

### 每个 Proposal 对应一个分支
Agent 在 Sandbox 中围绕自己的 Proposal Branch 工作。一个 Sandbox 不是一次 commit，而是一个可产生多次 commit 的临时工作副本。

Sandbox 环境

### 基础镜像先行，项目依赖后置
平台在云端维护默认基础镜像，至少包含 git 与基础运行工具。Sandbox 创建时可从缓存恢复，也可重新构建；当需要运行测试、构建或预览时，再根据项目配置准备依赖环境，必要时直接进入 Docker 或容器化执行模式。

生命周期

### Sandbox 默认短生命周期
Sandbox 主要用于当前任务的编码、测试与预览，不保留为长期运行实例。任务完成后自动销毁，避免环境污染、脏状态积累和多任务串扰。

**Main Branch**

项目当前稳定主线，作为 Project Workspace 的真源

→

**Proposal Branch**

从主线切出，每个 Proposal 单独对应一个分支

→

**Confirm**

审阅通过后 merge 回主线，形成新的版本记录

→

**Push**

当多个已确认 Proposal 组成稳定版本后，再统一同步到远端仓库

→

**Deploy**

基于已 push 或已确认的稳定版本，进入预览、测试或生产发布流程

 推荐约束：在最终稳定版本确认之前，Proposal Branch 默认不进入正式远端主仓库；如确有需要，可先进入平台内部暂存仓库，但不视为正式发布。同时，Sandbox 只负责临时执行，不承载长期持久化环境；真正长期保留的是 Project Workspace、Proposal 与 Version History。 

 AgentHub Workspace 方案示意页 | 适合用于设计评审、答辩讲解和产品结构对齐 

