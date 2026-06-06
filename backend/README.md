# Backend Environment Setup

This backend contains multiple Python services with different dependency
requirements. Create an independent virtual environment for each service and do
not rely on the old system Python.

## Recommended Python Version

- Prefer Python 3.12
- Python 3.13 may work for some parts, but dependency compatibility is worse
- Do not use the old system default Python 3.7 for this project

## Environment Layout

- `backend/gateway/.venv`
  - Used only for the gateway service
  - Installs `backend/gateway/requirements.txt`
- `backend/agent_service/.venv`
  - Used only for the FastAPI + AgentScope agent service
  - Installs `backend/agent_service/requirements.txt`

## Why Separate Environments

`gateway` and `agent_service` must stay in separate virtual environments.

- `gateway` keeps its own pinned FastAPI stack.
- `agent_service` is now AgentScope-first and lets pip resolve compatible
  FastAPI, Starlette, Uvicorn, and model SDK versions.

`agentscope` pulls in newer transitive dependencies like `mcp`,
`sse-starlette`, newer `starlette`, newer `uvicorn`, and newer model SDKs.
Because of that, `agent_service` should not keep a second optional AgentScope
environment or pin legacy runtime versions in parallel.

## Create Environments

If `py -3.12` is available:

```powershell
py -3.12 -m venv E:\Github\EchoMind\backend\gateway\.venv
py -3.12 -m venv E:\Github\EchoMind\backend\agent_service\.venv
```

If the Python launcher cannot find 3.12, replace `py -3.12` with the absolute
path of your installed Python 3.12 executable.

Example:

```powershell
D:\Python312\python.exe -m venv E:\Github\EchoMind\backend\gateway\.venv
```

## Install Dependencies

### Gateway

```powershell
E:\Github\EchoMind\backend\gateway\.venv\Scripts\python.exe -m pip install -r E:\Github\EchoMind\backend\gateway\requirements.txt
```

### Agent Service

```powershell
E:\Github\EchoMind\backend\agent_service\.venv\Scripts\python.exe -m pip install -r E:\Github\EchoMind\backend\agent_service\requirements.txt
```

If the network is slow, use a mirror:

```powershell
E:\Github\EchoMind\backend\gateway\.venv\Scripts\python.exe -m pip install -r E:\Github\EchoMind\backend\gateway\requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300
```

## Verify Environments

Check Python version:

```powershell
E:\Github\EchoMind\backend\gateway\.venv\Scripts\python.exe --version
E:\Github\EchoMind\backend\agent_service\.venv\Scripts\python.exe --version
```

Check dependency consistency:

```powershell
E:\Github\EchoMind\backend\gateway\.venv\Scripts\python.exe -m pip check
E:\Github\EchoMind\backend\agent_service\.venv\Scripts\python.exe -m pip check
```

## Start Services

### Start Gateway

```powershell
cd E:\Github\EchoMind\backend
E:\Github\EchoMind\backend\gateway\.venv\Scripts\python.exe -m uvicorn gateway.main:app --port 8000
```

### Start Agent Service

```powershell
cd E:\Github\EchoMind\backend
E:\Github\EchoMind\backend\agent_service\.venv\Scripts\python.exe -m uvicorn agent_service.main:app --port 8001
```

## Notes

- Do not install `agentscope` into `backend/gateway/.venv`
- `backend/agent_service/.venv` is the only supported runtime environment for
  the agent service
- If dependency resolution changes in future AgentScope releases, update
  `backend/agent_service/requirements.txt` rather than creating a second venv
