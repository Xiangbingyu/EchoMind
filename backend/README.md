# Backend Environment Setup

This backend contains multiple Python services with different dependency
requirements. To avoid package conflicts, create an independent virtual
environment for each service.

## Recommended Python Version

- Prefer Python 3.12
- Python 3.13 may work for some parts, but dependency compatibility is worse
- Do not use the old system default Python 3.7 for this project

## Environment Layout

- `backend/gateway/.venv`
  - Used only for the gateway service
  - Installs `backend/gateway/requirements.txt`
- `backend/agent_service/.venv`
  - Used only for the FastAPI agent service
  - Installs `backend/agent_service/requirements.txt`
- `backend/agent_service/.venv-agentscope`
  - Optional
  - Used only for AgentScope experiments or a future standalone agent process
  - Installs `backend/agent_service/requirements-agentscope.txt`

## Why Separate Environments

`gateway` and `agent_service` use FastAPI with pinned versions such as:

- `fastapi==0.115.0`
- `starlette==0.38.6`
- `uvicorn==0.30.6`

`agentscope` pulls in newer transitive dependencies like `mcp`,
`sse-starlette`, newer `starlette`, and newer `uvicorn`, which can break the
FastAPI services if they share the same virtual environment.

## Create Environments

If `py -3.12` is available:

```powershell
py -3.12 -m venv E:\Github\EchoMind\backend\gateway\.venv
py -3.12 -m venv E:\Github\EchoMind\backend\agent_service\.venv
py -3.12 -m venv E:\Github\EchoMind\backend\agent_service\.venv-agentscope
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

### Optional AgentScope Environment

```powershell
E:\Github\EchoMind\backend\agent_service\.venv-agentscope\Scripts\python.exe -m pip install -r E:\Github\EchoMind\backend\agent_service\requirements-agentscope.txt
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
E:\Github\EchoMind\backend\agent_service\.venv-agentscope\Scripts\python.exe -m pip check
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
- Do not install `agentscope` into `backend/agent_service/.venv` unless you are
  ready to resolve version conflicts yourself
- If `agent_service` later needs real AgentScope integration, prefer running it
  in a separate process with `.venv-agentscope`
