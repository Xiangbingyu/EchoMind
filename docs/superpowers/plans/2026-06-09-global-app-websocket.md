# Global App WebSocket Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single app-level WebSocket connection that stays open across `Messages` and `Workspace`, with session subscription and structured chat send events.

**Architecture:** Keep the existing session-scoped WebSocket route in place for compatibility, but add a new `/ws/app` route plus subscription-aware connection management on the backend. On the frontend, introduce an app-level socket provider above both pages, then migrate `Messages` to consume it while keeping the current HTTP bootstrap flow for session data.

**Tech Stack:** FastAPI, Starlette WebSocket, Python unittest/TestClient, React, React Router, Context API, Vitest, Testing Library

---

## File Map

### Backend

- Modify: `backend/gateway/ws/manager.py`
  Responsibility: track app-level WebSocket connections, active session subscriptions, and session broadcasts.
- Modify: `backend/gateway/ws/routes.py`
  Responsibility: add `/ws/app`, parse structured client events, subscribe connections to sessions, and reuse existing snapshot / dispatch helpers.
- Modify: `backend/tests/test_gateway_dual_ws_api.py`
  Responsibility: cover `/ws/app`, subscription behavior, structured send behavior, and compatibility expectations.

### Frontend

- Create: `frontend/src/context/AppSocketContext.jsx`
  Responsibility: own the single app-level WebSocket connection, reconnect policy, `subscribeSession`, `sendEvent`, and event listener registration.
- Modify: `frontend/src/layouts/MainLayout.jsx`
  Responsibility: mount the app socket provider around routed content.
- Modify: `frontend/src/pages/Messages/Messages.jsx`
  Responsibility: stop creating its own WebSocket, subscribe active session through the provider, consume provider events, and send structured events.
- Create: `frontend/src/context/AppSocketContext.test.jsx`
  Responsibility: verify singleton connection lifecycle and provider API behavior.
- Modify: `frontend/src/App.test.jsx`
  Responsibility: verify the routed shell mounts with provider in place.
- Modify: `frontend/src/pages/Messages/Messages.test.jsx`
  Responsibility: cover provider-driven subscription and structured chat send behavior.

## Task 1: Upgrade backend connection manager for app-level subscriptions

**Files:**
- Modify: `backend/gateway/ws/manager.py`
- Test: `backend/tests/test_gateway_dual_ws_api.py`

- [ ] **Step 1: Write the failing manager-level websocket behavior tests**

Add tests near `DualChannelWebsocketTests` in `backend/tests/test_gateway_dual_ws_api.py` for these behaviors:

```python
    def test_app_websocket_only_receives_events_after_subscribe(self):
        with self.client.websocket_connect('/ws/app') as ws:
            response = self.client.post(
                '/internal/callback',
                json={
                    'session_id': 'session-1',
                    'type': 'agent.token',
                    'data': 'hello',
                },
            )

            self.assertEqual(response.status_code, 200)
            with self.assertRaises(Exception):
                ws.receive_json(timeout=0.1)

    def test_app_websocket_switches_subscription_target(self):
        with self.client.websocket_connect('/ws/app') as ws:
            ws.send_json({'type': 'session.subscribe', 'session_id': 'session-1'})
            _ = ws.receive_json()
            _ = ws.receive_json()
            _ = ws.receive_json()

            ws.send_json({'type': 'session.subscribe', 'session_id': 'session-2'})
            _ = ws.receive_json()
            _ = ws.receive_json()
            _ = ws.receive_json()

            response = self.client.post(
                '/internal/callback',
                json={
                    'session_id': 'session-2',
                    'type': 'agent.token',
                    'data': 'second',
                },
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(ws.receive_json()['data'], 'second')
```

Use the same `FakeClient` / `patch('gateway.ws.routes.httpx.AsyncClient', ...)` pattern already used in this file so snapshot delivery is deterministic.

- [ ] **Step 2: Run the backend websocket tests to verify they fail**

Run: `python -m pytest backend/tests/test_gateway_dual_ws_api.py -k app_websocket -v`

Expected: FAIL because `/ws/app` does not exist and the manager has no subscription model.

- [ ] **Step 3: Implement minimal subscription-aware manager methods**

Update `backend/gateway/ws/manager.py` to support both legacy session-route connections and app-route connections:

```python
import json
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._app_connections: set[WebSocket] = set()
        self._app_subscriptions: dict[WebSocket, str] = {}

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self._connections.setdefault(session_id, []).append(ws)

    async def connect_app(self, ws: WebSocket):
        await ws.accept()
        self._app_connections.add(ws)

    def disconnect(self, session_id: str, ws: WebSocket):
        conns = self._connections.get(session_id, [])
        if ws in conns:
            conns.remove(ws)
        if not conns and session_id in self._connections:
            self._connections.pop(session_id)

    def disconnect_app(self, ws: WebSocket):
        self._app_connections.discard(ws)
        self._app_subscriptions.pop(ws, None)

    def subscribe(self, ws: WebSocket, session_id: str):
        self._app_subscriptions[ws] = session_id

    async def broadcast(self, session_id: str, event: dict):
        payload = json.dumps(event, ensure_ascii=False)

        for ws in list(self._connections.get(session_id, [])):
            try:
                await ws.send_text(payload)
            except WebSocketDisconnect:
                self.disconnect(session_id, ws)

        for ws, subscribed_session_id in list(self._app_subscriptions.items()):
            if subscribed_session_id != session_id:
                continue
            try:
                await ws.send_text(payload)
            except WebSocketDisconnect:
                self.disconnect_app(ws)
```

Keep legacy `connect(session_id, ws)` behavior intact.

- [ ] **Step 4: Run the focused backend websocket tests to verify they pass**

Run: `python -m pytest backend/tests/test_gateway_dual_ws_api.py -k app_websocket -v`

Expected: PASS for the new subscription tests.

- [ ] **Step 5: Commit**

```bash
git add backend/gateway/ws/manager.py backend/tests/test_gateway_dual_ws_api.py
git commit -m "feat: add app websocket subscriptions"
```

## Task 2: Add `/ws/app` route with structured protocol handling

**Files:**
- Modify: `backend/gateway/ws/routes.py`
- Modify: `backend/tests/test_gateway_dual_ws_api.py`

- [ ] **Step 1: Write the failing route/protocol tests**

Extend `backend/tests/test_gateway_dual_ws_api.py` with tests for:

```python
    def test_app_websocket_subscribe_sends_chat_and_workspace_snapshots(self):
        with patch('gateway.ws.routes.httpx.AsyncClient', return_value=FakeClient()):
            with self.client.websocket_connect('/ws/app') as ws:
                ws.send_json({'type': 'session.subscribe', 'session_id': 'session-1'})

                first_event = ws.receive_json()
                second_event = ws.receive_json()
                third_event = ws.receive_json()

                self.assertEqual(first_event['type'], 'message.history.sync')
                self.assertEqual(second_event['type'], 'workspace.snapshot')
                self.assertEqual(third_event['type'], 'workspace.tree.snapshot')

    def test_app_websocket_chat_send_dispatches_agent_run(self):
        with patch('gateway.ws.routes._dispatch_agent_run', new=AsyncMock()) as dispatch_run:
            with self.client.websocket_connect('/ws/app') as ws:
                ws.send_json({'type': 'chat.send', 'session_id': 'session-1', 'content': 'hello'})

                dispatch_run.assert_awaited_once_with(session_id='session-1', text='hello')

    def test_app_websocket_invalid_event_returns_error(self):
        with self.client.websocket_connect('/ws/app') as ws:
            ws.send_json({'type': 'chat.send', 'session_id': 'session-1', 'content': ''})
            event = ws.receive_json()
            self.assertEqual(event['type'], 'error')
```

Reuse the fake snapshot helper classes already present in this test file instead of introducing new fixture layers.

- [ ] **Step 2: Run the focused route tests to verify they fail**

Run: `python -m pytest backend/tests/test_gateway_dual_ws_api.py -k "subscribe_sends_chat or chat_send_dispatches or invalid_event" -v`

Expected: FAIL because `/ws/app` is not implemented and no structured protocol is parsed.

- [ ] **Step 3: Implement `/ws/app` and structured event parsing**

Update `backend/gateway/ws/routes.py` by keeping existing helpers and legacy route, then add:

```python
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect


async def _send_error(ws: WebSocket, message: str):
    await ws.send_json({'type': 'error', 'data': message})


@router.websocket('/ws/app')
async def app_ws(ws: WebSocket):
    await manager.connect_app(ws)
    try:
        await ws.send_json({'type': 'app.ready', 'data': 'ok'})
        while True:
            raw_message = await ws.receive_text()

            try:
                payload = json.loads(raw_message)
            except json.JSONDecodeError:
                await _send_error(ws, 'invalid websocket payload')
                continue

            event_type = payload.get('type')
            session_id = payload.get('session_id', '')

            if event_type == 'session.subscribe':
                if not session_id:
                    await _send_error(ws, 'session_id is required')
                    continue
                manager.subscribe(ws, session_id)
                await _send_chat_snapshot(session_id=session_id, ws=ws)
                await _send_workspace_snapshot(session_id=session_id, ws=ws)
                continue

            if event_type == 'chat.send':
                content = str(payload.get('content', '')).strip()
                if not session_id:
                    await _send_error(ws, 'session_id is required')
                    continue
                if not content:
                    await _send_error(ws, 'content is required')
                    continue
                await _dispatch_agent_run(session_id=session_id, text=content)
                continue

            await _send_error(ws, 'unsupported event type')
    except WebSocketDisconnect:
        manager.disconnect_app(ws)
```

Do not remove or rewrite `session_ws`; compatibility is part of the plan.

- [ ] **Step 4: Run the focused route tests to verify they pass**

Run: `python -m pytest backend/tests/test_gateway_dual_ws_api.py -k "subscribe_sends_chat or chat_send_dispatches or invalid_event" -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/gateway/ws/routes.py backend/tests/test_gateway_dual_ws_api.py
git commit -m "feat: add global app websocket route"
```

## Task 3: Add frontend app-level socket provider

**Files:**
- Create: `frontend/src/context/AppSocketContext.jsx`
- Create: `frontend/src/context/AppSocketContext.test.jsx`
- Modify: `frontend/src/layouts/MainLayout.jsx`

- [ ] **Step 1: Write the failing provider tests**

Create `frontend/src/context/AppSocketContext.test.jsx` with tests like:

```jsx
import React from 'react';
import { render, screen } from '@testing-library/react';
import { AppSocketProvider, useAppSocket } from './AppSocketContext';

function Probe() {
  const { connectionStatus, subscribeSession, sendEvent } = useAppSocket();

  return (
    <>
      <span>{connectionStatus}</span>
      <button onClick={() => subscribeSession('session-1')}>subscribe</button>
      <button onClick={() => sendEvent({ type: 'chat.send', session_id: 'session-1', content: 'hello' })}>
        send
      </button>
    </>
  );
}

it('opens exactly one websocket connection for the provider lifecycle', () => {
  const WebSocketMock = vi.fn(() => ({
    readyState: 1,
    close: vi.fn(),
    send: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));

  vi.stubGlobal('WebSocket', WebSocketMock);
  render(
    <AppSocketProvider>
      <Probe />
    </AppSocketProvider>,
  );

  expect(WebSocketMock).toHaveBeenCalledTimes(1);
});
```

Add a second test asserting `subscribeSession('session-1')` sends `{"type":"session.subscribe","session_id":"session-1"}` and `sendEvent(...)` sends the serialized structured event.

- [ ] **Step 2: Run the provider tests to verify they fail**

Run: `npm test -- AppSocketContext.test.jsx`

Expected: FAIL because the context file does not exist.

- [ ] **Step 3: Implement the provider and mount it in the layout**

Create `frontend/src/context/AppSocketContext.jsx` with a minimal provider API:

```jsx
import React, { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { createWsUrl } from '../utils/api';

const AppSocketContext = createContext(null);

export function AppSocketProvider({ children }) {
  const socketRef = useRef(null);
  const listenersRef = useRef(new Set());
  const [connectionStatus, setConnectionStatus] = useState('connecting');

  useEffect(() => {
    const ws = new WebSocket(createWsUrl('/ws/app'));
    socketRef.current = ws;
    setConnectionStatus('connecting');

    function handleOpen() {
      setConnectionStatus('open');
    }

    function handleError() {
      setConnectionStatus('error');
    }

    function handleClose() {
      setConnectionStatus('closed');
    }

    function handleMessage(event) {
      const payload = JSON.parse(event.data);
      listenersRef.current.forEach((listener) => listener(payload));
    }

    ws.addEventListener('open', handleOpen);
    ws.addEventListener('error', handleError);
    ws.addEventListener('close', handleClose);
    ws.addEventListener('message', handleMessage);

    return () => {
      ws.removeEventListener('open', handleOpen);
      ws.removeEventListener('error', handleError);
      ws.removeEventListener('close', handleClose);
      ws.removeEventListener('message', handleMessage);
      ws.close();
      socketRef.current = null;
    };
  }, []);

  const value = useMemo(() => ({
    connectionStatus,
    sendEvent(event) {
      const ws = socketRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        return false;
      }
      ws.send(JSON.stringify(event));
      return true;
    },
    subscribeSession(sessionId) {
      const ws = socketRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN || !sessionId) {
        return false;
      }
      ws.send(JSON.stringify({ type: 'session.subscribe', session_id: sessionId }));
      return true;
    },
    addListener(listener) {
      listenersRef.current.add(listener);
      return () => listenersRef.current.delete(listener);
    },
  }), [connectionStatus]);

  return <AppSocketContext.Provider value={value}>{children}</AppSocketContext.Provider>;
}

export function useAppSocket() {
  const value = useContext(AppSocketContext);
  if (!value) {
    throw new Error('useAppSocket must be used within AppSocketProvider');
  }
  return value;
}
```

Update `frontend/src/layouts/MainLayout.jsx` to wrap `<Sidebar />` and `<Outlet />` with `<AppSocketProvider>`.

- [ ] **Step 4: Run the provider tests to verify they pass**

Run: `npm test -- AppSocketContext.test.jsx App.test.jsx`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/context/AppSocketContext.jsx frontend/src/context/AppSocketContext.test.jsx frontend/src/layouts/MainLayout.jsx frontend/src/App.test.jsx
git commit -m "feat: add app socket provider"
```

## Task 4: Migrate `Messages` to the global app socket

**Files:**
- Modify: `frontend/src/pages/Messages/Messages.jsx`
- Create: `frontend/src/pages/Messages/Messages.test.jsx`

- [ ] **Step 1: Write the failing message-page integration tests**

Create `frontend/src/pages/Messages/Messages.test.jsx` with tests covering:

```jsx
it('subscribes the active session through the app socket provider', async () => {
  const subscribeSession = vi.fn();
  const addListener = vi.fn(() => vi.fn());
  const sendEvent = vi.fn();

  vi.mock('../../context/AppSocketContext', () => ({
    useAppSocket: () => ({
      connectionStatus: 'open',
      subscribeSession,
      addListener,
      sendEvent,
    }),
  }));

  global.fetch = vi.fn((input) => {
    const url = String(input);
    if (url.includes('/api/sessions?type=single')) {
      return Promise.resolve({ ok: true, json: async () => [{ id: 'session-1', title: 'Test', project_workspace_id: 'project-1', workspace_id: 'ws-1' }] });
    }
    if (url.includes('/api/sessions/session-1/messages')) {
      return Promise.resolve({ ok: true, json: async () => [] });
    }
    if (url.includes('/api/sessions/session-1')) {
      return Promise.resolve({ ok: true, json: async () => ({ id: 'session-1', project_workspace_id: 'project-1', workspace_id: 'ws-1' }) });
    }
    if (url.includes('/api/projects/project-1')) {
      return Promise.resolve({ ok: true, json: async () => ({ id: 'project-1', path: 'E:/repo' }) });
    }
    throw new Error(`Unexpected request: ${url}`);
  });

  render(<Messages />);

  await waitFor(() => {
    expect(subscribeSession).toHaveBeenCalledWith('session-1');
  });
});
```

Add a second test that types into the message box and asserts `sendEvent` is called with `{ type: 'chat.send', session_id: 'session-1', content: 'hello' }`.

- [ ] **Step 2: Run the page tests to verify they fail**

Run: `npm test -- Messages.test.jsx`

Expected: FAIL because `Messages.jsx` still imports `createWsUrl`, owns `socketRef`, and sends raw text.

- [ ] **Step 3: Implement the minimal page migration**

Update `frontend/src/pages/Messages/Messages.jsx` to:

```jsx
import { useAppSocket } from '../../context/AppSocketContext';
```

Remove:

```jsx
import { API_BASE_URL, createWsUrl, fetchJson } from '../../utils/api';
const socketRef = useRef(null);
```

Replace with:

```jsx
import { API_BASE_URL, fetchJson } from '../../utils/api';

const { connectionStatus, subscribeSession, addListener, sendEvent } = useAppSocket();
```

Change the `activeChat` effect so it:

- keeps the existing HTTP `Promise.all([...])` bootstrap
- removes `new WebSocket(...)`, `ws.onmessage`, `ws.onerror`, `ws.onclose`, and cleanup that closes a socket
- registers a provider listener via `const removeListener = addListener((payload) => { ...existing event switch... });`
- calls `subscribeSession(activeChat.id)` once bootstrap completes or once `connectionStatus === 'open'`

Update `handleSend` to:

```jsx
  function handleSend() {
    const text = inputValue.trim();
    if (!text || !activeChat) {
      return;
    }

    const sent = sendEvent({
      type: 'chat.send',
      session_id: activeChat.id,
      content: text,
    });

    if (!sent) {
      setChatError('实时连接未建立，暂时无法发送消息');
      return;
    }

    setChatError('');
    setChatStatus('');
    setTaskState('');
    setSending(true);
    setChatMessages((current) => [
      ...current,
      { id: `user-${Date.now()}`, role: 'user', content: text, pending: false },
    ]);
    setInputValue('');
  }
```

Keep the existing payload-to-state mapping logic intact; only change the event source.

- [ ] **Step 4: Run the page tests to verify they pass**

Run: `npm test -- Messages.test.jsx`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Messages/Messages.jsx frontend/src/pages/Messages/Messages.test.jsx
git commit -m "feat: use global app socket in messages"
```

## Task 5: Full regression verification

**Files:**
- Modify: `frontend/src/App.test.jsx`
- Modify: `backend/tests/test_gateway_dual_ws_api.py`

- [ ] **Step 1: Add the final regression expectations**

In `frontend/src/App.test.jsx`, add one assertion that rendering the routed app shell does not create duplicate providers during initial navigation.

In `backend/tests/test_gateway_dual_ws_api.py`, keep the legacy `/ws/session/{session_id}` snapshot tests and add one explicit compatibility test:

```python
    def test_legacy_session_websocket_still_receives_callback_events(self):
        with self.client.websocket_connect('/ws/session/session-1') as ws:
            response = self.client.post(
                '/internal/callback',
                json={'session_id': 'session-1', 'type': 'agent.token', 'data': 'hello'},
            )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(ws.receive_json()['type'], 'agent.token')
```

- [ ] **Step 2: Run targeted backend and frontend regressions**

Run: `python -m pytest backend/tests/test_gateway_dual_ws_api.py -v`
Expected: PASS

Run: `npm test -- App.test.jsx Messages.test.jsx Workspace.test.jsx WorkspaceBrowser.test.jsx WorkspaceResourceDialog.test.jsx`
Expected: PASS

- [ ] **Step 3: Run lint and production build**

Run: `npm run lint`
Expected: PASS with zero errors or warnings

Run: `npm run build`
Expected: PASS and output under `frontend/dist`

- [ ] **Step 4: Review working tree before final commit**

Run:

```bash
git status
git diff -- backend/gateway/ws/manager.py backend/gateway/ws/routes.py backend/tests/test_gateway_dual_ws_api.py frontend/src/context/AppSocketContext.jsx frontend/src/context/AppSocketContext.test.jsx frontend/src/layouts/MainLayout.jsx frontend/src/pages/Messages/Messages.jsx frontend/src/pages/Messages/Messages.test.jsx frontend/src/App.test.jsx
```

Expected: only intended global WebSocket changes are present.

- [ ] **Step 5: Commit**

```bash
git add backend/gateway/ws/manager.py backend/gateway/ws/routes.py backend/tests/test_gateway_dual_ws_api.py frontend/src/context/AppSocketContext.jsx frontend/src/context/AppSocketContext.test.jsx frontend/src/layouts/MainLayout.jsx frontend/src/pages/Messages/Messages.jsx frontend/src/pages/Messages/Messages.test.jsx frontend/src/App.test.jsx docs/superpowers/specs/2026-06-09-global-app-websocket-design.md docs/superpowers/plans/2026-06-09-global-app-websocket.md
git commit -m "feat: add global app websocket"
```
