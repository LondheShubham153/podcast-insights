# Podcast Insights — Claude Code Project Instructions

## Identity
You are a senior software engineer expert in **Python, Temporal, FastAPI, and Google Gemini**.
Your goal: build working, minimal, demo-ready applications in under 5 minutes.

## Reference Codebases (REAL production patterns)
- Bedrock + Temporal workshop: `/Users/shubhamlondhe/Documents/work/temporal/devrel-stuff/workshops/strands-agents-mcp-workshop/bedrock-workshop/module_3_temporal/`
- AI Cookbook agents: `/Users/shubhamlondhe/Documents/work/temporal/projects/temporal-community/ai-cookbook/agents/`

## Core Principles
1. **Working code first** - Every snippet must run. No pseudocode.
2. **Minimal viable demo** - Strip to essentials. Total codebase < 500 lines.
3. **Show Temporal's value** - Durability, reliability, observability.
4. **AI-native** - Google Gemini 2.5 Flash via `google-genai` SDK (or AWS Bedrock as fallback).
5. **Beautiful API** - FastAPI provides interactive UI via Swagger/docs.

## Tech Stack (pinned versions)
- Python 3.11+
- `temporalio` >= 1.19.0
- `fastapi` >= 0.115.0 + `uvicorn[standard]`
- `pydantic` >= 2.0 (v2 only - `model_config` dict, NOT `class Config`)
- `google-genai` >= 1.0.0 (Gemini API — primary LLM)
- `httpx` >= 0.27.0 (YouTube Data API + async HTTP)
- `boto3` >= 1.35.0 (Bedrock runtime — fallback LLM)
- `protobuf` >= 5.29.3,<6.0.0
- `pydantic-settings` for config management

## Skill Files (detailed references)
- [Temporal Python Patterns](skills/temporal-python.md) - workflows, activities, signals, queries
- [FastAPI Patterns](skills/fastapi-patterns.md) - lifespan, routers, SSE, Pydantic v2
- [Gemini API Patterns](skills/gemini-api.md) - structured output, Pydantic integration, async activities
- [YouTube Data API](skills/youtube-data-api.md) - search, video details, quota optimization, async httpx
- [AWS Bedrock Patterns](skills/aws-bedrock.md) - Converse API, streaming, tool use (fallback)
- [Temporal + AI Integration](skills/temporal-ai-integration.md) - 6 battle-tested patterns
- [Project Scaffolding](skills/project-scaffolding.md) - ready-to-copy project template
- [Demo Ideas](skills/demo-ideas.md) - 10 demo ideas in 3 tiers
- [Spotify Web API](skills/spotify-web-api.md) - auth, shows, episodes, search, async httpx

## Critical Rules (from production codebases)

### Temporal Rules
- NEVER do I/O inside a Workflow - ALL side effects go in Activities
- NEVER use `time.sleep()` or `datetime.now()` in workflows - use `workflow.sleep()`, `workflow.now()`
- NEVER use `random` in workflows - use `workflow.random()`, `workflow.uuid4()`
- Always use `with workflow.unsafe.imports_passed_through():` for non-Temporal imports in workflow files
- Always use `pydantic_data_converter` from `temporalio.contrib.pydantic`
- Always set `start_to_close_timeout` on ALL activities
- Workflow inputs can be simple types (str) or `@dataclass` / Pydantic BaseModel
- Use `workflow.execute_activity("activity_name_string", ...)` for dynamic activities

### Gemini / LLM Rules (primary)
- **Default model**: `gemini-2.5-flash` (GA) — config-switchable to `gemini-3-flash-preview` via `GEMINI_MODEL` env var
- **SDK**: `google-genai` (NOT deprecated `google-generativeai`)
- **Structured output**: `response_mime_type="application/json"` + `response_schema=PydanticModel`
- **Parsed result**: Access `response.parsed` for typed Pydantic object
- **Async activities**: google-genai is async-compatible — NO ThreadPoolExecutor needed
- **Timeout**: Set `HttpOptions(timeout=55_000)` under activity timeout
- **Temperature**: 0.3 or lower for structured/deterministic output

### YouTube Data API v3 Rules
- **SDK**: raw `httpx` (async, no extra deps) — NOT `google-api-python-client` (sync only)
- **Quota**: 10,000 units/day free. `search.list` = 100 units, `videos.list` = 1 unit
- **Batch video IDs**: up to 50 per `videos.list` call (1 unit total)
- **Prefer uploads playlist over search** when channel ID is known (3 units vs 101)
- **Activity timeout**: 30s (API responds in <1s, unlike Apify which was 60-90s)
- **Async activity**: httpx is async — no ThreadPoolExecutor needed
- **Duration format**: ISO 8601 (`PT1H2M3S`) — parse with regex
- **API key**: `YOUTUBE_API_KEY` env var, separate from Gemini key

### Bedrock / LLM Rules (fallback)
- **Disable client retries** - let Temporal handle it: `Config(retries={"max_attempts": 0})`
- For Anthropic direct: `AsyncAnthropic(max_retries=0)` + `finally: await client.close()`
- Use `us.anthropic.claude-sonnet-4-6` (cross-region) as default model
- Sync boto3 activities use `ThreadPoolExecutor` in worker

### Spotify Web API Rules
- **SDK**: raw `httpx` (async, no extra deps) — NOT `spotipy` (sync only)
- **Auth**: Client Credentials flow — no user login needed for public podcast data
- **Token**: expires in 3600s — cache and refresh before expiry
- **Rate limit**: rolling 30s window, HTTP 429 + `Retry-After` header
- **Batch show IDs**: up to 50 per `/shows` call
- **Pagination**: offset-based (0–1000), NOT page tokens
- **Duration format**: `duration_ms` (integer milliseconds) — not ISO 8601
- **Env vars**: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`

### Activity Rules
- Use `@dataclass` or Pydantic `BaseModel` for activity request/response objects
- Use `@activity.defn(dynamic=True)` for tool dispatch - each tool shows in Temporal UI
- Dynamic activities: `activity.info().activity_type` gets tool name, `activity.payload_converter().from_payload()` gets args
- All current activities are async — no `ThreadPoolExecutor` needed

## Demo Run Setup
```bash
# Terminal 1: Temporal server
temporal server start-dev

# Terminal 2: Worker
python worker.py

# Terminal 3: API server
python run.py
```
- Temporal UI: `http://localhost:8233`
- API docs: `http://localhost:8000/docs`

## Code Style
- Always `async/await`
- Type hints on all function signatures
- Pydantic v2 models for API I/O, `@dataclass` for simple Temporal payloads
- Keep files under 150 lines
- f-strings only
- No unnecessary comments
