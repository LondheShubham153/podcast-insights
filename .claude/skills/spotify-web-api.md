# Spotify Web API — Patterns for Temporal Activities

## 1. Setup

### App Credentials
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create an app → select **Web API**
3. Copy **Client ID** and **Client Secret**
4. Set env vars: `SPOTIFY_CLIENT_ID=...`, `SPOTIFY_CLIENT_SECRET=...`

### Python SDK Choice
Use **raw httpx** (async, zero extra deps, already in stack). Do NOT use:
- `spotipy` — sync only, no async support
- `tekore` — extra dependency, overkill for activity-level calls

## 2. Authentication — Client Credentials Flow

Server-to-server flow (no user login needed). Access public podcast/show/episode data.

```
POST https://accounts.spotify.com/api/token
```

| Header | Value |
|--------|-------|
| `Authorization` | `Basic <base64(client_id:client_secret)>` |
| `Content-Type` | `application/x-www-form-urlencoded` |

| Body Param | Value |
|------------|-------|
| `grant_type` | `client_credentials` |

**Response:**
```json
{
  "access_token": "NgCXRKc...MzYjw",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Token Helper
```python
import base64
import httpx

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"

async def get_spotify_token(client_id: str, client_secret: str) -> str:
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            SPOTIFY_TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
        )
        resp.raise_for_status()
        return resp.json()["access_token"]
```

**Key points:**
- Token expires in **3600s** (1 hour) — cache and refresh before expiry
- Client credentials flow does NOT require user scopes
- Sufficient for all public show/episode/search endpoints

## 3. Rate Limits

| Fact | Value |
|------|-------|
| Rate window | **Rolling 30 seconds** |
| Dev mode limit | Lower (unspecified exact number) |
| Extended quota | Apply via Developer Dashboard |
| Rate limit response | **HTTP 429** |
| Retry header | `Retry-After` (seconds) |

**No daily quota cap** like YouTube — rate-limited per rolling window only.

### Temporal Strategy
- Let Temporal retry on 429 — `RetryPolicy(backoff_coefficient=2.0)`
- Parse `Retry-After` header for optimal wait time
- Activity timeout: 30s (API responds in <1s)

## 4. Endpoint Reference

Base URL: `https://api.spotify.com/v1`

All requests require: `Authorization: Bearer <access_token>`

### search — Find shows/episodes by keyword
```
GET /search
```
| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `q` | string | required | Search query. Supports field filters: `artist:`, `year:`, `genre:` |
| `type` | string | required | Comma-separated: `show`, `episode`, `track`, `artist`, `album` |
| `market` | string | — | ISO 3166-1 alpha-2 (e.g., `US`) |
| `limit` | int | 20 | 0–50 |
| `offset` | int | 0 | 0–1000 |

**For podcasts use:** `type=show` or `type=episode`

### shows/{id} — Get show details
```
GET /shows/{id}
```
| Param | Type | Notes |
|-------|------|-------|
| `id` | path, string | Spotify show ID (e.g., `38bS44xjbVVZ3No3ByF1dJ`) |
| `market` | query, string | Optional ISO country code |

**Response fields:**
- `id`, `name`, `description`, `html_description`
- `publisher`, `total_episodes`, `explicit`
- `images[]` (url, height, width)
- `languages[]` (ISO 639-1)
- `episodes` (paginated — href, limit, next, offset, total, items[])

### shows/{id}/episodes — List show episodes
```
GET /shows/{id}/episodes
```
| Param | Type | Default | Notes |
|-------|------|---------|-------|
| `id` | path, string | required | Show ID |
| `market` | query, string | — | ISO country code |
| `limit` | int | 20 | 0–50 |
| `offset` | int | 0 | Pagination offset |

**Episode object fields:**
- `id`, `name`, `uri`, `type`
- `description`, `html_description`
- `duration_ms` (integer — milliseconds)
- `release_date` (string — `YYYY-MM-DD`, precision varies)
- `release_date_precision` (`year`, `month`, `day`)
- `explicit` (boolean)
- `images[]` (url, height, width)
- `languages[]` (ISO 639-1)
- `audio_preview_url` (nullable, deprecated)
- `is_playable` (boolean, market-dependent)
- `external_urls.spotify` (web link)

### episodes/{id} — Get single episode
```
GET /episodes/{id}
```
| Param | Type | Notes |
|-------|------|-------|
| `id` | path, string | Episode ID (e.g., `512ojhOuo1ktJprKbVcKyQ`) |
| `market` | query, string | Optional ISO country code |

Returns full episode object + nested `show` object.

### shows — Get multiple shows (batch)
```
GET /shows
```
| Param | Type | Notes |
|-------|------|-------|
| `ids` | query, string | Comma-separated show IDs (max 50) |
| `market` | query, string | Optional |

## 5. Async Activity Pattern (httpx)

```python
import httpx
from temporalio import activity

SPOTIFY_BASE = "https://api.spotify.com/v1"

@activity.defn
async def search_podcasts(request: SpotifySearchRequest) -> SpotifySearchResult:
    token = await get_spotify_token(client_id, client_secret)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: Search for shows
        resp = await client.get(f"{SPOTIFY_BASE}/search", headers=headers, params={
            "q": request.query,
            "type": "show",
            "market": "US",
            "limit": request.max_results,
        })
        resp.raise_for_status()
        shows = resp.json()["shows"]["items"]

        # Step 2: Get episodes for top show
        if shows:
            show_id = shows[0]["id"]
            resp = await client.get(
                f"{SPOTIFY_BASE}/shows/{show_id}/episodes",
                headers=headers,
                params={"market": "US", "limit": 50},
            )
            resp.raise_for_status()
            episodes = resp.json()["items"]

        return parse_spotify_results(shows, episodes)
```

### Key points:
- **Async native** — no ThreadPoolExecutor needed
- **Batch show IDs** — up to 50 per `/shows` call
- **Timeout**: 30s (API responds in <1s)
- **Token caching** — refresh only when expired (every 3600s)
- **Let Temporal retry** — raise on HTTP errors, Temporal handles retries

## 6. Duration Formatting

Spotify returns `duration_ms` as integer milliseconds. Convert:
```python
def format_duration(ms: int) -> str:
    total_secs = ms // 1000
    h, remainder = divmod(total_secs, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
```

## 7. Pagination

```python
all_episodes = []
offset = 0
while True:
    resp = await client.get(
        f"{SPOTIFY_BASE}/shows/{show_id}/episodes",
        headers=headers,
        params={"market": "US", "limit": 50, "offset": offset},
    )
    data = resp.json()
    all_episodes.extend(data["items"])
    if not data["next"]:
        break
    offset += 50
```

Spotify uses **offset-based** pagination (not page tokens like YouTube).

## 8. Error Handling

| HTTP Code | Meaning | Temporal Action |
|-----------|---------|-----------------|
| 400 | Bad request (invalid params) | Non-retryable — fix code |
| 401 | Expired or invalid token | Retryable — refresh token and retry |
| 403 | Forbidden (insufficient scope) | Non-retryable — check auth flow |
| 404 | Show/episode not found | Non-retryable |
| 429 | Rate limited | Retryable — respect `Retry-After` header |
| 5xx | Server error | Retryable (Temporal default) |

## Key Rules
1. **Use Client Credentials flow** — no user login needed for public podcast data
2. **Cache tokens** — expires in 3600s, don't re-auth on every request
3. **Batch show lookups** — up to 50 IDs per `/shows` call
4. **Offset pagination** — NOT page tokens; max offset is 1000
5. **`duration_ms`** — integer milliseconds (not ISO 8601 like YouTube)
6. **Activity timeout**: 30s (API is fast)
7. **httpx async** — no ThreadPoolExecutor needed in Worker
8. **Let Temporal retry** — raise on errors, set `RetryPolicy(maximum_attempts=3)`
