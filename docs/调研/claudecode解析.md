# agenthub可以采取的措施
+ 全局md，项目级md，模块化md
+ 缓存设计
+ 对于评分节点可以采用fork模式，多维度判断。
+ 对于串行的任务可以，比方说用户@后，由产品agent总结，来修改需求文档，然后各个开发agent只读需求文档来进行开发，人工介入的话也可以修改这个需求文档。
+ 可以结合teammate和worktree，前后端agent分别读一个接口文档开始开发。<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/67387315/1778667787388-e82d91a5-7fe4-423b-807a-a52f0a8b8030.png)
+ claude是需要用户自己开五个对话，然后并行处理，我们可以在多个agent分配工作的时候就直接这样实现。
+ 对于命令的权限配置，优先我们系统中限制一些危害我们服务器的命令（allowedits），其次是就是按照配置来源优先级，从组织到自身的配置，在同层中使用auto



# 心得
## md规范
+ 全局md，记录该用户的编码风格，偏好。
+ 项目级md，定义该项目的架构决策和约定（我的感觉是借口啊之类的）。
+ 模块化md，记录该模块的规则（我的感觉是具体怎么实现）。

claude会在每次对话（非会话）加载一次**全量md**。

**tip**：各个文档的大小不宜过大。

## 缓存
**前缀缓存（****<font style="color:rgb(26, 28, 31);">prefix cache</font>****）**，可以大大降低成本，可以按顺序加载全局md，项目级md，接着才是模块化md，最后才是该agent的一些系统提示词和用户的提示词。

**优点**：

1. 降成本，重复大上下文不必每次全额计算。
2. 降延迟，长前缀处理更快。
3. 适合并行，多agent共享同前缀时，边际成本下降。
4. 对场文档/大代码库场景收益大。

**缺点**（1，2，4我感觉不算啥效果上的缺点，只是能不能省钱）：

1. 非强保证，是否命中，命中多少由平台决策。
2. 对改动敏感，前缀早位置小改动会显著影响命中率。
3. 可能会诱导“过度塞上下文”，并非越长越好，噪音会影响质量。（我的理解是为了使缓存命中，导致用户不敢去修改前缀的一些规则，或是多加了很多与这次对话无关的信息，导致出现噪音的现象）
4. 工程上仍有合并/依赖成本，缓存只优化token计算，不解决协作复杂度。
5. **<font style="color:rgb(26, 28, 31);">上下文污染被高频复用</font>**<font style="color:rgb(26, 28, 31);">  
</font><font style="color:rgb(26, 28, 31);">如果共享前缀里本来就有错误假设/歧义，它会被所有子 agent 一起继承，错误被放大。</font>

**提高命中率**：

1. 固定前缀，把稳定内容放在最前面（规则，术语，项目背景）。
2. 变动后置，把本次任务差异放在后面。
3. 模版化，统一系统提示和任务骨架，减少随机改写。
4. 统一快照，多agent使用同一版本文档和代码摘要。
5. 减少前缀抖动，不要频繁修改前半段措辞，顺序，格式。
6. 按依赖并行，让可并行任务共享前缀，不可并行任务串行。

## 三种模式（fork，teammate，worktree）
**fork模式**

+ 定义：从父agent的上下文直接分出子agent，起点基本保持一致。
+ 工作方式  
1. 继承同一份上下文（规则、历史、项目信息）。  
2. 子agent各自执行不同任务。  
3.最后父agent汇总结果并集成。
+ 优点：  
1.启动快。  
2.前缀服用量高，缓存收益最好。  
3.适合统一问题拆成多个并行子问题。
+ 缺点：  
1.多个子agent同时修改统一文件，冲突概率高。  
2.共享前提如果有误，所有子agent复制放大。  
3.需要统一风格和决策。
+ 使用场景：  
1.并行代码审计（安全，性能，可维护性可以分开来看）  
2.并行写测试（单测，集成测，边界测可分开来写）  
3.并行定位多个报错跟因。
+ 实操建议  
1.先划清ownership，减少重叠修改。  
2.子任务提示词要明显区分职责。  
3.父agent保留最终裁决权。

**teammate模式**

+ 定义：更像独立同事协作。不是继承上下文，而是通过消息、文档、文件交换信息。
+ 工作方式：  
1.每个agen有相对独立工作上下文。  
2.通过任务单，说明文档，输出报告协同。  
3.以约定接口对接成果。
+ 优点：  
1.职责边界清晰。  
2.非技术任务和技术任务可并行（方案，文档，实现）。  
3.适合长周期协作和人工介入。
+ 缺点：  
1.上下文天然共享较弱，沟通成本更高。  
2.可能重复解释背景。  
3.缓存收益不如fork稳定。
+ 适用场景：  
1.一个agent做需求澄清，一个做实现，一个做发布说明。  
2.跨角色协作（产品，测试，开发流程分工话）。  
3.需要交付物驱动的协作（报告，清单，评审结论）。
+ 实操建议：  
1.用固定模版交接（输入，输出，验收标准）。  
2.所有结论必须服证据（文件，日志，测试结果）。  
3.明确谁负责最终集成。

**worktree模式**

+ 定义：每个agent在独立的git worktree/分支工作，代码物理隔离。
+ 工作方式：  
1.从同一株分枝派生多个worktree。  
2.子agent在各自目录独立修改代码，跑测试。  
3.最后通过merge/cherry-pick集成回主线。
+ 优点：  
1.并行改代码冲突显著减小。  
2.隔离性强，试验性改动风险低。  
3.回滚，比对，验收更清楚。
+ 缺点：  
1.环境和集成成本高于fork。  
2.合并阶段仍可能有语义冲突。  
需要更严格的分支和CI纪律。
+ 适用场景：  
1.多个较大改动并行推进。  
2.重构，bugfix，测试补齐同时进行。  
3.需要高可追溯性的工程团队流程。
+ 实操建议：  
1.按模块分worktree，避免交叉改动文件。  
2.每个worktree都跑最小必要测试再合并提交。  
3.设集成窗口和冲突处理负责人。

**<font style="color:rgb(26, 28, 31);">三者怎么选（最实用）</font>**

1. <font style="color:rgb(26, 28, 31);">追求速度和缓存收益：优先</font><font style="color:rgb(26, 28, 31);"> </font><font style="color:rgb(26, 28, 31);">fork</font><font style="color:rgb(26, 28, 31);">。</font>
2. <font style="color:rgb(26, 28, 31);">追求角色协作和流程清晰：用</font><font style="color:rgb(26, 28, 31);"> </font><font style="color:rgb(26, 28, 31);">teammate</font><font style="color:rgb(26, 28, 31);">。</font>
3. <font style="color:rgb(26, 28, 31);">追求代码隔离和并行开发稳定性：用</font><font style="color:rgb(26, 28, 31);"> </font><font style="color:rgb(26, 28, 31);">worktree</font><font style="color:rgb(26, 28, 31);">。</font>
4. <font style="color:rgb(26, 28, 31);">常见组合：</font><font style="color:rgb(26, 28, 31);">fork</font><font style="color:rgb(26, 28, 31);"> 做并行分析 + </font><font style="color:rgb(26, 28, 31);">worktree</font><font style="color:rgb(26, 28, 31);"> 做并行落地。</font>

## 权限配置
对于**权限系统**

+ policy = Managed settings（企业托管策略，最高优先级）
+ flag = 命令行参数（本次会话临时覆盖）
+ local = .claude/settings.local.json（本机、当前仓库私有）
+ project = .claude/settings.json（仓库共享配置）
+ user = ~/.claude/settings.json（你个人全局配置）

三种**权限模式**

1. **bypass**
    - 含义：基本跳过权限检查，尽量不打断。
    - 特点：最快，但风险最高。
    - 适用：临时、受控环境（例如你完全信任当前任务和仓库）。
    - 不适用：生产环境、含敏感数据的机器、多人共享环境。
2. **allowEdits**
    - 含义：默认放行工作目录内常见编辑动作；其他高风险操作仍可能要确认或被拦。
    - 特点：编码体验顺滑，安全性比 bypass 高很多。
    - 适用：日常开发主力模式（改代码、改文档、跑常见命令）。
3. **auto**
    - 含义：每个操作会结合规则 + 分类器判断是否放行。
    - 特点：平衡“少打断”和“风险控制”，通常是最均衡模式。
    - 适用：你希望自动化程度高，但又不想完全放开时。

auto中也可以细分：

1. hard_deny：硬拒绝，最高
2. soft_deny：默认拒，但可被明确意图或 allow 例外放宽（取决于配置）
3. allow：允许列表

## 上下文管理
### <font style="color:rgb(25, 27, 31);">五种压缩策略</font>
+ <font style="color:rgb(25, 27, 31);">microcompact —— 基于时间清理旧的工具结果</font>
+ <font style="color:rgb(25, 27, 31);">context collapse —— 对一段对话进行摘要压缩</font>
+ <font style="color:rgb(25, 27, 31);">session memory —— 提取关键上下文到文件</font>
+ <font style="color:rgb(25, 27, 31);">full compact —— 对整个历史进行总结</font>
+ <font style="color:rgb(25, 27, 31);">PTL truncation —— 丢弃最早的一组消息</font>

### <font style="color:rgb(25, 27, 31);">分层权限控制</font>
### <font style="color:rgb(25, 27, 31);">流式中断与重试机制</font>
## hook
不仅仅是在提示词中拼接约束，而是在节点执行完成后加上验证节点









## 参考文本
> [https://zhuanlan.zhihu.com/p/2022605516262614921](https://zhuanlan.zhihu.com/p/2022605516262614921)
>

### **<font style="color:rgb(25, 27, 31);">3.1. CLAUDE.md 每一轮都会被加载</font>**
<font style="color:rgb(25, 27, 31);">这是你能做的杠杆最大的一件事，但几乎没人用对。</font>

<font style="color:rgb(25, 27, 31);">大多数人的 CLAUDE.md 不是空的，就是写成了一本“圣经”。</font>

<font style="color:rgb(25, 27, 31);">但源代码显示：Claude Code 会在</font>**<font style="color:rgb(25, 27, 31);">每一次查询迭代</font>**<font style="color:rgb(25, 27, 31);">中读取你的</font>**<font style="color:rgb(25, 27, 31);"> </font>****<font style="color:rgb(25, 27, 31);">CLAUDE.md</font>**<font style="color:rgb(25, 27, 31);">，而不是只在会话开始时读取。</font>**<font style="color:rgb(25, 27, 31);">这意味着——每次你发消息，它都会重新读一遍你的指令</font>**<font style="color:rgb(25, 27, 31);">。</font>

<font style="color:rgb(25, 27, 31);">而且它有一整套层级结构：</font>

+ <font style="color:rgb(25, 27, 31);">~/.claude/CLAUDE.md —— 全局（你的编码风格、偏好）</font>
+ <font style="color:rgb(25, 27, 31);">./CLAUDE.md —— 项目级（架构决策、约定）</font>
+ <font style="color:rgb(25, 27, 31);">.claude/rules/*.md —— 模块化规则</font>
+ <font style="color:rgb(25, 27, 31);">CLAUDE.local.md —— 私有笔记（被 git 忽略）</font>

<font style="color:rgb(25, 27, 31);">你有 40,000 字符的空间，这非常多。但大多数人只用了 200。</font>

+ **<font style="color:rgb(25, 27, 31);">动态加载机制</font>**<font style="color:rgb(25, 27, 31);">：与大多数人的认知不同，Claude Code 会在每一次查询迭代中读取</font><font style="color:rgb(25, 27, 31);"> </font>[<font style="color:rgb(9, 64, 142);">CLAUDE.md</font>](https://link.zhihu.com/?target=http%3A//claude.md/)<font style="color:rgb(25, 27, 31);">，而不是只在会话开始时读取。这意味着每次用户发送消息，系统都会重新读一遍配置指令。</font>
+ **<font style="color:rgb(25, 27, 31);">大容量配置空间</font>**<font style="color:rgb(25, 27, 31);">：系统提供了 40,000 字符的配置空间，但大多数用户只用了 200 字符。这个巨大的配置空间为复杂项目的定制化提供了可能。</font>

<font style="color:rgb(25, 27, 31);">把你的架构决策写进去。文件约定写进去。测试模式写进去。以及那些“绝对不要这样做”的规则。</font>

<font style="color:rgb(25, 27, 31);">模型会在</font>**<font style="color:rgb(25, 27, 31);">每一轮</font>**<font style="color:rgb(25, 27, 31);">读取它们。</font>

<font style="color:rgb(25, 27, 31);">这就是 Claude Code 从“一个通用助手”变成“一个真正懂你代码库的专属助手”的关键差别。</font>

<font style="color:rgb(25, 27, 31);">如果你读完只做一件事，那就做这个。</font>

  


### **<font style="color:rgb(25, 27, 31);">3.2. 子 Agent 共享 prompt 缓存（</font>**<font style="color:rgb(25, 27, 31);">多智能体并行执行架构，</font>**<font style="color:rgb(25, 27, 31);">并行几乎是免费的）</font>**
<font style="color:rgb(25, 27, 31);">这是最让我震惊的一点。</font>

<font style="color:rgb(25, 27, 31);">mal_shaik 特别强调了 Claude Code 的多智能体并行执行机制。他指出，</font>**<font style="color:rgb(25, 27, 31);">子 Agent 共享缓存的机制，则直接把并行执行的成本压缩到接近单线程水平，这在当前大模型产品中并不常见</font>**<font style="color:rgb(25, 27, 31);">。</font>

<font style="color:rgb(25, 27, 31);">这一机制的技术优势包括：</font>

+ **<font style="color:rgb(25, 27, 31);">成本优化</font>**<font style="color:rgb(25, 27, 31);">：当 Claude Code fork 一个子 Agent 时，它会创建一个与父上下文字节级完全一致的副本，而 API 会对这个上下文做缓存。因此，同时启动 5 个 Agent 处理不同任务，成本几乎和 1 个 Agent 顺序执行差不多。</font>
+ <font style="color:rgb(25, 27, 31);">当 Claude Code fork 一个子 Agent 时，它会创建一个与父上下文</font>**<font style="color:rgb(25, 27, 31);">字节级完全一致</font>**<font style="color:rgb(25, 27, 31);">的副本。而 API 会对这个上下文做缓存。所以——同时启动 5 个 Agent 处理不同任务，成本几乎和 1 个 Agent 顺序执行差不多。</font>

<font style="color:rgb(25, 27, 31);">再读一遍。</font>

<font style="color:rgb(25, 27, 31);">5 个 Agent，成本≈1 个。因为它们命中了同一个 prompt cache。</font>

<font style="color:rgb(25, 27, 31);">但大多数人是怎么用的？把 Claude Code 当成一个单线程打工人：</font>

<font style="color:rgb(25, 27, 31);">做一个任务 → 等 → 再给下一个任务。</font>

<font style="color:rgb(25, 27, 31);">而源码里，子 Agent 有三种执行模型：</font>

+ <font style="color:rgb(25, 27, 31);">fork —— 继承父上下文，缓存最优</font>
+ <font style="color:rgb(25, 27, 31);">teammate —— 在 tmux 或 iTerm 中开独立面板，通过文件“邮箱”通信</font>
+ <font style="color:rgb(25, 27, 31);">worktree —— 每个 Agent 一个独立 git worktree，各自分支隔离</font>

**<font style="color:rgb(25, 27, 31);">实际应用场景</font>**<font style="color:rgb(25, 27, 31);">：用户完全可以让 Claude Code 同时跑 5 个 Agent：一个做安全审计，一个重构认证模块，一个写测试，一个更新文档，一个修 bug—— 全部并行执行，共享缓存。</font>

<font style="color:rgb(25, 27, 31);">这个架构本来就是为并行设计的。</font>

<font style="color:rgb(25, 27, 31);">你却把它当单线程用，简直是在浪费。  
</font>

### **<font style="color:rgb(25, 27, 31);">3.3.</font>****<font style="color:rgb(25, 27, 31);"> </font>**[**<font style="color:rgb(9, 64, 142);">权限系统</font>**](https://zhida.zhihu.com/search?content_id=272334058&content_type=Article&match_order=1&q=%E6%9D%83%E9%99%90%E7%B3%BB%E7%BB%9F&zhida_source=entity)**<font style="color:rgb(25, 27, 31);">是用来“配置”的，不是用来“点确认”的</font>**
<font style="color:rgb(25, 27, 31);">mal_shaik 在推文中提到了 Claude Code 的权限系统设计，指出这是一个被大多数用户误解的重要功能。他强调，</font>**<font style="color:rgb(25, 27, 31);">每当 Claude Code 弹出 "是否允许这个操作？" 而你点了 "是"，这不是一个功能，这是配置失败</font>**<font style="color:rgb(25, 27, 31);">。</font>

<font style="color:rgb(25, 27, 31);">权限系统的核心设计包括：</font>

+ **<font style="color:rgb(25, 27, 31);">五层权限配置体系</font>**<font style="color:rgb(25, 27, 31);">：</font>
    - <font style="color:rgb(25, 27, 31);">policy > flag > local > project > user</font>
+ **<font style="color:rgb(25, 27, 31);">权限模式</font>**<font style="color:rgb(25, 27, 31);">：</font>
    - <font style="color:rgb(25, 27, 31);">bypass —— 完全不做权限检查（危险但极快）</font>
    - <font style="color:rgb(25, 27, 31);">allowEdits —— 自动允许工作目录内的文件编辑</font>
    - <font style="color:rgb(25, 27, 31);">auto（新模式）—— 每个操作都由一个 LLM 分类器判断（最平衡）</font>
+ **<font style="color:rgb(25, 27, 31);">配置示例</font>**<font style="color:rgb(25, 27, 31);">：用户可以在～/.claude/settings.json 中用 glob 模式定义哪些操作默认允许：</font>

```plain
{
  "permissions": {
    "allow": [
      "Bash(npm *)",
      "Bash(git *)", 
      "Edit(src/**)",
      "Write(src/**)"
    ]
  }
}
```

<font style="color:rgb(25, 27, 31);">auto 模式也支持你自定义 allow / deny 列表。源码显示，它会并行触发多个“裁决器”：用户点击、hook 分类器、bridge 等，</font>**<font style="color:rgb(25, 27, 31);">谁先返回就用谁的结果</font>**<font style="color:rgb(25, 27, 31);">。</font>

<font style="color:rgb(25, 27, 31);">你每点一次“允许”，都是在浪费时间。</font>

<font style="color:rgb(25, 27, 31);">配置一次，就别再点了。</font>

### **<font style="color:rgb(25, 27, 31);">3.4.</font>****<font style="color:rgb(25, 27, 31);"> </font>**[<font style="color:rgb(9, 64, 142);">上下文管理</font>](https://zhida.zhihu.com/search?content_id=272334058&content_type=Article&match_order=1&q=%E4%B8%8A%E4%B8%8B%E6%96%87%E7%AE%A1%E7%90%86&zhida_source=entity)<font style="color:rgb(25, 27, 31);">(</font>**<font style="color:rgb(25, 27, 31);">一共有 5 种上下文压缩策略)：</font>**
**<font style="color:rgb(25, 27, 31);">context 压力是个真实存在的问题</font>**

<font style="color:rgb(25, 27, 31);">mal_shaik 在推文中指出，</font>**<font style="color:rgb(25, 27, 31);">CC 源码也侧面印证了当前大模型工程的一个现实瓶颈：上下文管理已经成为系统复杂度的核心来源</font>**<font style="color:rgb(25, 27, 31);">。他进一步分析，五种压缩策略、分层权限控制、流式中断与重试机制，本质上都是在对抗 "上下文膨胀" 和 "系统不稳定性" 这两个问题。</font>

<font style="color:rgb(25, 27, 31);">这一洞察揭示了当前大模型应用面临的核心技术挑战：</font>

+ **<font style="color:rgb(25, 27, 31);">上下文管理复杂性</font>**<font style="color:rgb(25, 27, 31);">：随着模型能力的提升和应用场景的复杂化，如何有效管理和利用上下文信息成为系统设计的关键难题。</font>
+ **<font style="color:rgb(25, 27, 31);">技术解决方案</font>**<font style="color:rgb(25, 27, 31);">：Claude Code 采用了多种策略来应对这一挑战，包括五种上下文压缩策略：</font>
    - <font style="color:rgb(25, 27, 31);">microcompact —— 基于时间清理旧的工具结果</font>
    - <font style="color:rgb(25, 27, 31);">context collapse —— 对一段对话进行摘要压缩</font>
    - <font style="color:rgb(25, 27, 31);">session memory —— 提取关键上下文到文件</font>
    - <font style="color:rgb(25, 27, 31);">full compact —— 对整个历史进行总结</font>
    - <font style="color:rgb(25, 27, 31);">PTL truncation —— 丢弃最早的一组消息</font>

<font style="color:rgb(25, 27, 31);">这其实在传递一个很重要的信号：</font>**<font style="color:rgb(25, 27, 31);">上下文溢出是工程团队投入了大量精力解决的核心问题。</font>**

<font style="color:rgb(25, 27, 31);">对你来说，这意味着：</font>

+ <font style="color:rgb(25, 27, 31);">主动使用</font><font style="color:rgb(25, 27, 31);"> </font>`<font style="color:rgb(25, 27, 31);background-color:rgb(248, 248, 250);">/compact</font>`<font style="color:rgb(25, 27, 31);">。不要等系统自动压缩，把你在意的上下文一起“误杀”。</font>
+ <font style="color:rgb(25, 27, 31);">默认窗口是 200K tokens，但你可以通过使用</font><font style="color:rgb(25, 27, 31);"> </font>`<font style="color:rgb(25, 27, 31);background-color:rgb(248, 248, 250);">[1m]</font>`<font style="color:rgb(25, 27, 31);"> </font><font style="color:rgb(25, 27, 31);">模型后缀扩展到 100 万 tokens。在跨多文件的大规模重构中，这非常关键。</font>
+ <font style="color:rgb(25, 27, 31);">长会话会逐渐积累“session memory”——包括任务描述、文件列表、工作流状态、错误和经验总结的结构化信息。这也是为什么</font>**<font style="color:rgb(25, 27, 31);">继续一个会话比重新开一个更有价值</font>**<font style="color:rgb(25, 27, 31);">。</font>
+ <font style="color:rgb(25, 27, 31);">大型工具输出会被存储到磁盘，模型只会看到一个 8KB 的预览。如果你粘贴一个超大文件，模型可能只看到其中一小部分——所以输入要尽量聚焦。</font>

<font style="color:rgb(25, 27, 31);">真正把 Claude Code 用到极致的人，会把</font><font style="color:rgb(25, 27, 31);"> </font>`<font style="color:rgb(25, 27, 31);background-color:rgb(248, 248, 250);">/compact</font>`<font style="color:rgb(25, 27, 31);"> </font><font style="color:rgb(25, 27, 31);">当成游戏里的“手动存档点”：保留关键内容，清掉噪音，然后继续推进。</font>

### **<font style="color:rgb(25, 27, 31);">3.5. Hook 系统才是真正的扩展 API（25+ 生命周期事件）</font>**
<font style="color:rgb(25, 27, 31);">这是一个几乎没人知道的“高手功能”。</font>

<font style="color:rgb(25, 27, 31);">源码显示，有超过 25 个生命周期事件可以被你挂钩（hook）：</font>

+ <font style="color:rgb(25, 27, 31);">PreToolUse —— 任意工具执行前触发</font>
+ <font style="color:rgb(25, 27, 31);">PostToolUse —— 任意工具执行后触发</font>
+ <font style="color:rgb(25, 27, 31);">UserPromptSubmit —— 你发送消息时触发</font>
+ <font style="color:rgb(25, 27, 31);">SessionStart / SessionEnd —— 会话开始 / 结束</font>
+ <font style="color:rgb(25, 27, 31);">以及另外 20 多个事件</font>

<font style="color:rgb(25, 27, 31);">同时支持 5 种 Hook 类型：</font>

+ <font style="color:rgb(25, 27, 31);">command —— 执行 shell 命令</font>
+ <font style="color:rgb(25, 27, 31);">prompt —— 通过 LLM 注入上下文</font>
+ <font style="color:rgb(25, 27, 31);">agent —— 运行一个完整的 agent 校验流程</font>
+ <font style="color:rgb(25, 27, 31);">HTTP —— 调用 webhook</font>
+ <font style="color:rgb(25, 27, 31);">function —— 执行 JavaScript</font>

<font style="color:rgb(25, 27, 31);">你可以做什么？</font>

+ <font style="color:rgb(25, 27, 31);">每次写文件前自动跑 lint</font>
+ <font style="color:rgb(25, 27, 31);">每次修改后自动执行测试</font>
+ <font style="color:rgb(25, 27, 31);">自动把相关文档注入到每一个 prompt</font>
+ <font style="color:rgb(25, 27, 31);">任务完成后发 Slack 通知</font>
+ <font style="color:rgb(25, 27, 31);">在代码发布前校验安全规范</font>

<font style="color:rgb(25, 27, 31);">其中最离谱的是</font><font style="color:rgb(25, 27, 31);"> </font>`<font style="color:rgb(25, 27, 31);background-color:rgb(248, 248, 250);">UserPromptSubmit</font>`<font style="color:rgb(25, 27, 31);"> </font><font style="color:rgb(25, 27, 31);">这个 Hook：  
</font><font style="color:rgb(25, 27, 31);">你可以在</font>**<font style="color:rgb(25, 27, 31);">每一条消息发送时自动注入 additionalContext</font>**<font style="color:rgb(25, 27, 31);">。</font>

<font style="color:rgb(25, 27, 31);">这意味着什么？</font>

<font style="color:rgb(25, 27, 31);">你可以在每次提问时，自动附带测试结果、最近的 git diff、当前项目状态——而不需要手动复制粘贴。</font>

<font style="color:rgb(25, 27, 31);">这才是你构建“自定义开发环境”的方式——  
</font><font style="color:rgb(25, 27, 31);">不是写更好的 prompt，而是</font>**<font style="color:rgb(25, 27, 31);">直接改造系统本身的行为</font>**<font style="color:rgb(25, 27, 31);">。</font>

### **<font style="color:rgb(25, 27, 31);">3.6. 会话是持久化且可恢复的（</font>**<font style="color:rgb(25, 27, 31);">会话持久化与记忆系统，</font>**<font style="color:rgb(25, 27, 31);">别再每次都从零开始）</font>**
<font style="color:rgb(25, 27, 31);">mal_shaik 分析了 Claude Code 的会话管理机制，指出</font>**<font style="color:rgb(25, 27, 31);">会话持久化与 session memory 的设计，让上下文不再是一次性资源，而是可以累积、复用的长期资产</font>**<font style="color:rgb(25, 27, 31);">。</font>

<font style="color:rgb(25, 27, 31);">这一机制的关键特性包括：</font>

+ **<font style="color:rgb(25, 27, 31);">持久化存储</font>**<font style="color:rgb(25, 27, 31);">：每一段对话都会以 JSONL 格式保存到：~/.claude/projects/{hash}/{sessionId}.jsonl</font>
+ **<font style="color:rgb(25, 27, 31);">会话恢复能力</font>**<font style="color:rgb(25, 27, 31);">：系统支持：</font>
+ <font style="color:rgb(25, 27, 31);">--continue—— 继续上一次会话</font>
+ <font style="color:rgb(25, 27, 31);">--resume—— 指定恢复某个历史会话</font>
+ <font style="color:rgb(25, 27, 31);">--fork-session—— 从过去的对话分叉一个新分支</font>
+ **<font style="color:rgb(25, 27, 31);">记忆积累机制</font>**<font style="color:rgb(25, 27, 31);">：session memory 会在多次压缩中保留关键上下文，包括任务描述、文件列表、工作流状态、错误和经验总结的结构化信息。这种设计使得继续一个会话比重新开一个更有价值。</font>

<font style="color:rgb(25, 27, 31);">session memory 会在多次压缩中保留关键上下文：任务描述、文件列表、工作流状态、错误和经验。</font>

<font style="color:rgb(25, 27, 31);">但大多数人是怎么做的？</font>

<font style="color:rgb(25, 27, 31);">每次打开 Claude Code，都新开一个 session。</font>

<font style="color:rgb(25, 27, 31);">这相当于你每工作一小时，就把 IDE 关掉，再从零打开一次——之前做了什么、哪里失败了、学到了什么，全没了。</font>

<font style="color:rgb(25, 27, 31);">正确用法是：</font>

<font style="color:rgb(25, 27, 31);">用</font><font style="color:rgb(25, 27, 31);"> </font>`<font style="color:rgb(25, 27, 31);background-color:rgb(248, 248, 250);">--continue</font>`<font style="color:rgb(25, 27, 31);">。一直用。</font>

<font style="color:rgb(25, 27, 31);">让上下文不断积累，让 session memory 持续沉淀经验。</font>

<font style="color:rgb(25, 27, 31);">源码已经把这套机制搭好了，你不用，才是真的浪费。</font>

### **<font style="color:rgb(25, 27, 31);">3.7. 工具系统：60+ 工具 + 智能批处理执行（</font>**<font style="color:rgb(25, 27, 31);">工具调度与扩展机制</font>**<font style="color:rgb(25, 27, 31);">）</font>**
<font style="color:rgb(25, 27, 31);">mal_shaik 在推文中分析了 Claude Code 的工具系统架构。他指出，</font>**<font style="color:rgb(25, 27, 31);">Hook 系统提供了超过 25 个生命周期切入点，使其具备类似插件系统的扩展能力；MCP 工具的延迟加载机制，则意味着它天然可以接入外部服务生态，而不会牺牲基础性能</font>**<font style="color:rgb(25, 27, 31);">。</font>

<font style="color:rgb(25, 27, 31);">具体技术特点包括：</font>

+ **<font style="color:rgb(25, 27, 31);">丰富的工具类型</font>**<font style="color:rgb(25, 27, 31);">：Claude Code 内置了 60 多个工具，包括基础工具（文件操作、命令执行）、网络工具（网页获取、搜索）、高级工具（子智能体派生、MCP 协议调用）、协作工具等。</font>
+ **<font style="color:rgb(25, 27, 31);">智能调度机制</font>**<font style="color:rgb(25, 27, 31);">：工具调用分为两类：</font>
+ <font style="color:rgb(25, 27, 31);">concurrent（并发）—— 只读操作（读文件、搜索、glob 匹配）可以并行执行</font>
+ <font style="color:rgb(25, 27, 31);">serial（串行）—— 有修改行为的操作（编辑、写入、bash 命令）必须逐个执行，避免冲突</font>
+ **<font style="color:rgb(25, 27, 31);">扩展能力</font>**<font style="color:rgb(25, 27, 31);">：通过 MCP（Model Context Protocol）协议，可以接入外部服务生态。系统采用延迟加载机制，只有在真正需要时才加载 MCP 工具，因此即使接入 5 个 MCP Server，也不会拖慢每一次请求。</font>

<font style="color:rgb(25, 27, 31);">另外还有一个 ToolSearch 机制，用来动态发现 agent 还不知道的工具。</font>

<font style="color:rgb(25, 27, 31);">现实意义很直接：</font>

+ <font style="color:rgb(25, 27, 31);">如果你的工作流涉及外部系统（数据库、云服务、CI/CD），就把它们通过 MCP 接进来。底层架构会帮你处理复杂性，你只是在“白拿能力”。</font>

### **<font style="color:rgb(25, 27, 31);">3.8. 流式架构：随时打断，几乎没有成本（</font>**<font style="color:rgb(25, 27, 31);">流式架构与中断机制</font>**<font style="color:rgb(25, 27, 31);">）</font>**
<font style="color:rgb(25, 27, 31);">mal_shaik 特别分析了 Claude Code 的流式架构设计，这是一个看似简单但影响深远的技术特性：</font>

+ **<font style="color:rgb(25, 27, 31);">流式执行模型</font>**<font style="color:rgb(25, 27, 31);">：整个执行链路是基于 async generator 的，每一步都会以事件流的形式逐步输出。</font>
+ **<font style="color:rgb(25, 27, 31);">中断机制</font>**<font style="color:rgb(25, 27, 31);">：按下 Escape，可以干净地中断当前响应，同时不会丢失已有上下文。这种设计让用户可以随时纠正系统的执行方向，而无需承担任何成本。</font>
+ **<font style="color:rgb(25, 27, 31);">实际应用价值</font>**<font style="color:rgb(25, 27, 31);">：这种设计彻底改变了用户与系统的交互方式。用户不需要等待一个已经知道走偏的回答完成，而是可以立刻打断，重新引导。这就像结对编程时，如果搭档开始写错方向，你会直接说："等等，换个思路"。</font>

### **<font style="color:rgb(25, 27, 31);">3.9. 重试系统，比你想象得更“抗打”</font>**
<font style="color:rgb(25, 27, 31);">mal_shaik 分析了 Claude Code 的重试系统，指出这是一个 "比你想象得更抗打" 的工程化设计：</font>

+ **<font style="color:rgb(25, 27, 31);">重试策略</font>**<font style="color:rgb(25, 27, 31);">：</font>
    - <font style="color:rgb(25, 27, 31);">最多 10 次重试，带指数退避 + 抖动（基准 500ms）</font>
    - <font style="color:rgb(25, 27, 31);">遇到 401/403 自动刷新 OAuth token</font>
    - <font style="color:rgb(25, 27, 31);">模型自动降级：如果 Opus 连续 3 次 529 错误，会自动切到 Sonnet</font>
    - <font style="color:rgb(25, 27, 31);">流式输出 90 秒无响应，会自动切换为非流式</font>
    - <font style="color:rgb(25, 27, 31);">持久模式下支持 "无限重试"，最大退避 5 分钟</font>
+ **<font style="color:rgb(25, 27, 31);">设计理念</font>**<font style="color:rgb(25, 27, 31);">：这种设计背后的理念是，Claude Code 是可以 "放在那里跑" 的系统。API 抖动、限流、短暂故障 —— 它会自己处理，用户不需要盯着它。用户可以让它在后台跑，过一会回来拿结果。</font>

<font style="color:rgb(25, 27, 31);">这背后的设计意图很明确：</font>

**<font style="color:rgb(25, 27, 31);">Claude Code 是可以“放在那里跑”的系统。</font>**

<font style="color:rgb(25, 27, 31);">API 抖动、限流、短暂故障——它会自己处理，你不需要盯着它。</font>

<font style="color:rgb(25, 27, 31);">让它在后台跑，过一会回来拿结果就行。</font>

### <font style="color:rgb(25, 27, 31);">3.10 开发范式的转变</font>
<font style="color:rgb(25, 27, 31);">mal_shaik 在推文中强调了一个重要观点：</font>**<font style="color:rgb(25, 27, 31);">真正拉开用户差距的，并不是谁更会写 prompt，而是谁开始把 Claude Code 当作一套 "可配置的开发基础设施" 来使用</font>**<font style="color:rgb(25, 27, 31);">。</font>

<font style="color:rgb(25, 27, 31);">这种转变体现在以下几个方面：</font>

+ **<font style="color:rgb(25, 27, 31);">从提示词优化到系统配置</font>**<font style="color:rgb(25, 27, 31);">：传统的 AI 工具使用方式注重 prompt 工程，而 Claude Code 的高效使用需要掌握系统级的配置能力。</font>
+ **<font style="color:rgb(25, 27, 31);">关键能力要求</font>**<font style="color:rgb(25, 27, 31);">：</font>
    - <font style="color:rgb(25, 27, 31);">前置规则设计能力</font>
    - <font style="color:rgb(25, 27, 31);">并行任务拆分能力</font>
    - <font style="color:rgb(25, 27, 31);">自动化流程嵌入能力</font>
    - <font style="color:rgb(25, 27, 31);">跨会话的上下文经营能力</font>
+ **<font style="color:rgb(25, 27, 31);">实际应用价值</font>**<font style="color:rgb(25, 27, 31);">：那些能够充分利用 Claude Code 配置能力的用户，其工作效率可能比普通用户高 10 倍。这不是因为他们更会写提示词，而是因为他们掌握了系统的本质 —— 一个可配置的 Agent 编排平台。</font>

