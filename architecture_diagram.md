# 项目架构图（总览）

```mermaid
flowchart TD
    U[User]
    CLI[main_cli.py]
    WEB[main_web.py]
    API[FastAPI app/api/main.py]
    MCP[MCP Server mcp_server.py]
    HCLI[harness.cli / run_harness.py]

    subgraph H[Harness Layer]
      HINIT[Initializer]
      HEXE[Executor]
      HWS[Workspace<br/>harness/workspace/<run_id>]
      HREP[Report<br/>latest.json / latest.md]
      HCLI --> HINIT --> HWS
      HCLI --> HEXE
      HEXE <--> HWS
      HEXE --> HREP
    end

    subgraph F[FastAPI Gateway]
      MID[Auth / RateLimit / CORS / RequestId]
      ROUTE[Routes<br/>health/chat/stream/state/actions]
      AR[AgentRunner]
      API --> MID --> ROUTE --> AR
    end

    subgraph M[MCP Tools]
      MT1[healthz / research_search]
      MT2[chat / stream_chat / get_state]
      MT3[action_request_* / confirm / reject]
      MCP --> MT1
      MCP --> MT2
      MCP --> MT3
      MT2 --> AR
      MT3 --> AR
    end

    subgraph G[LangGraph Core]
      APP[create_agent_app]
      IR[intent_router]
      PL[planner]
      EX[executor]
      SY[synthesizer]
      CR[critic]
      APP --> IR --> PL --> EX --> SY --> CR
      CR -->|reject| EX
    end

    subgraph T[Tools and Capabilities]
      TOOL[tools.py<br/>dify/web/action_*]
      ACT[actions/<br/>policy/handlers/audit]
      VI[vision/]
      VO[voice/]
      MEM[memory/]
      EX --> TOOL
      TOOL --> ACT
      SY <--> VI
      SY <--> VO
      SY <--> MEM
    end

    subgraph S[Storage]
      DB[(SQLite checkpoint<br/>AGENT_DB_PATH)]
      AUD[(audit.log)]
      PROF[(user_profiles.json)]
      OUT[(action_outputs/*)]
      APP --> DB
      ACT --> AUD
      MEM --> PROF
      ACT --> OUT
    end

    U --> CLI --> APP
    U --> WEB --> APP
    U --> API
    U --> MCP
    HCLI --> API
    HCLI --> MCP
    HCLI --> APP
    AR --> APP
```

## 部署视角架构图

```mermaid
flowchart LR
    subgraph Client[Client Layer]
      BROWSER[Web Browser]
      CURL[API Client / curl / SDK]
      MCPCLIENT[MCP Client]
      DEV[Developer CLI]
    end

    subgraph AppHost[Application Host]
      subgraph Proc1[Process A]
        STREAMLIT[Streamlit UI<br/>main_web.py]
      end

      subgraph Proc2[Process B]
        FASTAPI[FastAPI + Uvicorn<br/>app/api/main.py]
        GW[Gateway Middleware<br/>Auth / RateLimit / CORS / RequestId]
        ROUTES[Routes<br/>/healthz /readyz /v1/sessions/*]
      end

      subgraph Proc3[Process C]
        MCP[MCP Server<br/>mcp_server.py]
      end

      subgraph Proc4[Process D]
        HARNESS[Harness CLI<br/>harness.cli / run_harness.py]
        HINIT[Initializer]
        HEXEC[Executor]
      end

      subgraph Core[Agent Runtime]
        AR[AgentRunner]
        LG[LangGraph App]
        NODES[intent/planner/executor/synthesizer/critic]
        TOOLS[tools.py<br/>dify/web/action_*]
      end

      subgraph Cap[Capabilities]
        ACTIONS[actions/<br/>policy handlers audit]
        MEMORY[memory/]
        VISION[vision/]
        VOICE[voice/]
      end

      subgraph Persist[Persistence]
        WS[(harness/workspace/<run_id>/*)]
        REP[(harness/report/latest.json|md)]
        DB[(SQLite checkpoint)]
        AUDIT[(audit.log)]
        PROFILE[(user_profiles.json)]
        OUT[(action_outputs/*)]
      end
    end

    BROWSER -->|HTTP| STREAMLIT
    BROWSER -->|HTTP| FASTAPI
    CURL -->|HTTP| FASTAPI
    MCPCLIENT -->|stdio MCP| MCP
    DEV -->|python -m ...| HARNESS

    FASTAPI --> GW --> ROUTES --> AR
    MCP --> AR
    STREAMLIT --> LG
    AR --> LG --> NODES --> TOOLS
    TOOLS --> ACTIONS
    NODES <--> MEMORY
    NODES <--> VISION
    NODES <--> VOICE

    LG --> DB
    ACTIONS --> AUDIT
    ACTIONS --> OUT
    MEMORY --> PROFILE

    HARNESS --> HINIT --> WS
    HARNESS --> HEXEC --> WS
    HEXEC --> REP
    HEXEC -->|entry=api| FASTAPI
    HEXEC -->|entry=mcp| MCP
    HEXEC -->|entry=local| LG
```

## 关键时序图：Chat 到待确认动作

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant API as FastAPI /v1/sessions/{id}/chat
    participant MW as Gateway Middleware
    participant AR as AgentRunner
    participant LG as LangGraph
    participant Tool as action_* tool
    participant Act as actions.handlers
    participant Audit as audit.log
    participant Store as session_store(in-memory)

    User->>API: POST /chat (message)
    API->>MW: request enter
    MW-->>API: pass (auth/ratelimit ok)

    API->>AR: run_chat(session_id, req)
    AR->>LG: stream(input_payload)

    LG->>Tool: invoke action_* (based on plan)
    alt requires confirmation
        Tool-->>LG: pending_confirmation + confirm_payload
        LG-->>AR: node updates(messages/tool payload)
        AR->>AR: parse action payload
        AR->>Store: append action_pending_queue(act_xxx)
        AR-->>API: snapshot(last_answer/task_runtime/pending queue)
        API-->>User: 200 ChatResponse
    else auto executable
        Tool->>Act: execute_confirmed_action(...)
        Act->>Audit: append executed/failed
        Act-->>Tool: result
        Tool-->>LG: executed/failed payload
        LG-->>AR: node updates
        AR->>Store: append action_execution_logs
        AR-->>API: snapshot
        API-->>User: 200 ChatResponse
    end
```

## 关键时序图：Confirm 动作

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant API as FastAPI /actions/{action_id}/confirm
    participant AR as AgentRunner
    participant Act as actions.handlers
    participant Audit as audit.log
    participant Store as session_store(in-memory)

    User->>API: POST /confirm(action_id)
    API->>AR: confirm_action(session_id, action_id, approve=true)

    AR->>Store: find action_pending_queue by action_id
    alt found
        AR->>Act: execute_confirmed_action(action, payload)
        Act->>Audit: append executed/failed
        Act-->>AR: result
        AR->>Store: remove pending action
        AR->>Store: append action_execution_logs
        AR->>Store: append pending_action_results
        AR-->>API: {ok:true, result:{status:executed|failed}}
        API-->>User: 200
    else not found
        AR-->>API: {ok:false, message:action_id not found}
        API-->>User: 404 MM404_ACTION_NOT_FOUND
    end
```

## 关键时序图：MCP 审批链路

```mermaid
sequenceDiagram
    autonumber
    participant Client as MCP Client
    participant MCP as mcp_server.py
    participant AR as AgentRunner
    participant Store as session_store(in-memory)
    participant Act as actions.handlers
    participant Audit as audit.log

    Client->>MCP: action_request_shell_command(session_id, command)
    MCP->>AR: request_action(...)
    AR->>Store: append action_pending_queue(act_xxx)
    AR->>Audit: append pending_confirmation
    AR-->>MCP: {ok:true, action_id:act_xxx}
    MCP-->>Client: queued

    Client->>MCP: confirm_action(session_id, act_xxx)
    MCP->>AR: confirm_action(..., approve=true)
    AR->>Act: execute_confirmed_action(...)
    Act->>Audit: append executed/failed
    AR->>Store: remove pending + append execution_logs
    AR-->>MCP: {ok:true, result:{status:executed|failed}}
    MCP-->>Client: confirm result
```
