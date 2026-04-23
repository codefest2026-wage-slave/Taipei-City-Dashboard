# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.

---

## Project Overview

Taipei City Dashboard is a data visualization platform by Taipei Urban Intelligence Center (TUIC). It is a monorepo with three main subsystems:

| Directory | Stack | Purpose |
|-----------|-------|---------|
| `Taipei-City-Dashboard-FE/` | Vue 3, Vite, Pinia, Mapbox GL | Frontend SPA |
| `Taipei-City-Dashboard-BE/` | Go, Gin, GORM, PostgreSQL, Redis | REST API backend |
| `Taipei-City-Dashboard-DE/` | Python, Apache Airflow | Data pipeline ETL |

## Local Development Setup

All services run via Docker Compose. Configuration lives in `docker/.env` (copy from ONBOARDING.md).

```bash
# 1. Create the shared Docker network (one-time)
docker network create --driver=bridge --subnet=192.168.128.0/24 --gateway=192.168.128.1 br_dashboard

# 2. Start databases and Qdrant
docker-compose -f docker/docker-compose-db.yaml up -d

# 3. Initialize frontend and backend environments
docker-compose -f docker/docker-compose-init.yaml up -d

# 4. Start frontend and backend services
docker-compose -f docker/docker-compose.yaml up -d

# 5. (Optional) Populate Qdrant vector DB from PostgreSQL data
docker compose --profile tools up vector-db-upgrade
```

Access at `http://localhost:8080`. To log in with admin: hold **Shift** and click the TUIC logo to switch to username/password form. Default credentials are set in `docker/.env` (`DASHBOARD_DEFAULT_Email` / `DASHBOARD_DEFAULT_PASSWORD`).

### Frontend (FE) — standalone dev

```bash
cd Taipei-City-Dashboard-FE
npm install
npm run dev       # dev server with hot reload
npm run lint      # ESLint with auto-fix
npm run build     # lint + production build
```

### Backend (BE) — standalone dev

```bash
cd Taipei-City-Dashboard-BE
go run main.go    # start server (requires env vars set)
go build ./...    # compile check
go test ./...     # run all tests
```

## Architecture

### Frontend

- **Entry**: `src/main.js` → `App.vue`
- **Router**: `src/router/index.js` — routes to views in `src/views/`
- **State (Pinia stores)**:
  - `contentStore` — dashboards, components, map layers, current dashboard state; primary store for data fetching
  - `mapStore` — Mapbox GL map instance, layer management (`addToMapLayerList` is the most critical flow)
  - `authStore` — JWT token, login state
  - `dialogStore` — which dialogs are open
  - `chatStore` — AI chat history
  - `adminStore` — admin panel data
- **`dashboardComponent/`** — reusable chart component library (BarChart, DonutChart, MapLegend, etc.); `DashboardComponent.vue` is the generic wrapper that selects the right chart based on config
- **API calls**: all HTTP via `src/router/axios.js` (configured base URL from `VITE_API_URL`)

### Backend

- **Entry**: `main.go` → `cmd/` (Cobra CLI) → `app/app.go` (`StartApplication`)
- **Startup sequence** (`app.go`): connect PostgreSQL (two DBs) + Redis → init cron jobs → init ONNX LM session → configure Gin router → start server
- **Two PostgreSQL databases**:
  - `dashboard` — city data, component data, chart data
  - `dashboardmanager` — users, dashboards config, issues, contributors
- **Routes** (`app/routes/router.go`): all under `/api/v1/`; groups: `auth`, `user`, `component`, `dashboard`, `issue`, `incident`, `contributor`, `chatlog`, `ai`, `lm`
- **Middleware**: `ValidateJWT` on all routes, `IsLoggedIn()` / `IsSysAdm()` for protected routes, rate limiting per route group
- **AI features** (`app/controllers/ai.go`, `app/controllers/qdrant.go`):
  - Local ONNX embedding model (path: `LM_MODEL_PATH`) + Qdrant vector DB for semantic search
  - TWCC AI Foundry LLM (OpenAI-compatible API) for chat; configured via `TWCC_*` env vars
- **Cron jobs**: `app/initial/` — scheduled data refresh tasks

### Data Engineering

- Apache Airflow DAGs in `Taipei-City-Dashboard-DE/dags/`
- Organized by project: `proj_city_dashboard/`, `proj_new_taipei_city_dashboard/`
- Shared operators in `operators/`, utilities in `utils/`

### Key env vars (docker/.env)

| Variable | Purpose |
|----------|---------|
| `VITE_MAPBOXTOKEN` | Mapbox GL access token |
| `TWCC_API_KEY` | LLM API key (TWCC AI Foundry, OpenAI-compatible) |
| `TWCC_MODEL` | LLM model name (default: `llama3.3-ffm-70b-16k-chat`) |
| `LM_MODEL_PATH` | Local ONNX embedding model path |
| `QDRANT_URL` / `QDRANT_API_KEY` | Vector DB for semantic chart search |
| `JWT_SECRET` | JWT signing secret |
| `DB_DASHBOARD_*` / `DB_MANAGER_*` | Two PostgreSQL connection configs |
