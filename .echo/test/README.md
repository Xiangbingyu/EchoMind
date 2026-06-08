# EchoMind

EchoMind 是一个多模块项目，当前仓库主要包含后端服务与设计文档。

## 目录结构

- `backend/`
  - Python 后端代码
  - 包含 `gateway`、`agent_service`、`git_service` 和测试脚本
- `docs/`
  - 设计文档、规格说明和实现草稿

## 后端模块

- `backend/gateway`
  - 对外 API 网关
  - 负责 REST API、WebSocket、会话消息落库、Git 相关接口
- `backend/agent_service`
  - Agent 运行服务
  - 负责加载会话历史、执行 Agent、流式回调 gateway
- `backend/git_service`
  - 预留 Git 相关模块
  - 当前主要 Git 接口实现仍在 `gateway` 中
- `backend/tests`
  - 集成测试脚本

## 运行方式

当前推荐为不同服务使用各自独立的虚拟环境：

- `backend/gateway/.venv`
- `backend/agent_service/.venv`
- `backend/tests/.venv`

详细环境说明、依赖安装和启动命令见：

- [backend/README.md](file:///E:/Github/EchoMind/backend/README.md)

## 当前状态

- `gateway` 与 `agent_service` 已可联调
- WebSocket 消息流和消息落库链路已打通
- Git 提案相关接口已接通并通过测试

## 说明

- 建议使用 Python 3.12
- 不建议使用系统默认的旧版 Python 3.7
- 本地开发配置应写入 `backend/.env`，不要提交到仓库
