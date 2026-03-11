# Podcast Insights Agent

A durable AI pipeline that analyzes YouTube podcast channels and delivers personalized video recommendations based on your interests.

Built with **Temporal** for reliability, **Gemini** for intelligence, and **FastAPI** for a beautiful developer experience.

---

## How It Works

1. You provide a **channel name** and your **interests**
2. The agent searches YouTube for podcast-length videos on that channel
3. Gemini parses your interests into structured keywords and topics
4. Videos are ranked by relevance and the channel is summarized
5. You get scored recommendations, key insights, and content tone analysis

Each step runs as a Temporal activity — if anything fails, it retries automatically. No data is lost.

---

## Tech Stack

| Layer | Technology | Role |
|---|---|---|
| Orchestration | Temporal | Durable workflows, retries, observability |
| LLM | Google Gemini 2.5 Flash | Structured output for ranking and summarization |
| API | FastAPI + Uvicorn | REST endpoints with interactive Swagger docs |
| YouTube | YouTube Data API v3 via httpx | Async video search and metadata fetching |
| Validation | Pydantic v2 | Request/response schemas and config management |
| Frontend | Tailwind CSS + Vanilla JS | Dark-themed UI with real-time progress tracking |

---

## Prerequisites

- Python 3.11+
- [Temporal CLI](https://docs.temporal.io/cli#install)
- [Google Gemini API key](https://aistudio.google.com/apikey)
- [YouTube Data API v3 key](https://console.cloud.google.com/apis/credentials)

---

## Quick Start

### 1. Clone and install

```
git clone git@github.com:LondheShubham153/podcast-insights.git
cd podcast-insights
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 2. Configure environment

```
cp .env.example .env
```

Edit `.env` and add your API keys.

### 3. Start Temporal

```
temporal server start-dev
```

### 4. Start the worker

```
python worker.py
```

### 5. Run the API server

```
python run.py
```

---

## Access Points

| URL | What |
|---|---|
| `http://localhost:8000` | Web UI |
| `http://localhost:8000/docs` | Swagger API docs |
| `http://localhost:8233` | Temporal dashboard |

---

## API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/analyze` | Start a new analysis workflow |
| GET | `/api/status/{id}` | Poll workflow progress |
| GET | `/api/result/{id}` | Fetch completed results |
| GET | `/api/health` | Health check |

---

## Pipeline Stages

| Stage | Activity | What Happens |
|---|---|---|
| Search | `search_videos` | Finds podcast-length videos on YouTube (>10 min) |
| Parse | `extract_interests` | Gemini extracts structured keywords from your input |
| Rank | `rank_videos` | Gemini scores each video 0-100 based on relevance |
| Summarize | `generate_summary` | Gemini produces channel insights and content tone |

Rank and Summarize run **in parallel** for speed.

---

## Project Structure

```
podcast-insights/
  activities/       Temporal activities (YouTube scraper, Gemini analyzer)
  app/              FastAPI application (routes, config, lifespan)
  models/           Pydantic schemas for API and workflow data
  workflows/        Temporal workflow definitions
  static/           Web UI
  worker.py         Temporal worker entrypoint
  run.py            API server entrypoint
```

---

## Environment Variables

| Variable | Required | Default |
|---|---|---|
| `GEMINI_API_KEY` | Yes | — |
| `YOUTUBE_API_KEY` | Yes | — |
| `GEMINI_MODEL` | No | `gemini-2.5-flash` |
| `TEMPORAL_HOST` | No | `localhost:7233` |
| `TASK_QUEUE` | No | `podcast-insights` |

---

## License

MIT
