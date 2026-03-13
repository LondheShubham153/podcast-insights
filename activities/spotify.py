import base64

import httpx
from temporalio import activity

from app.config import settings
from models.schemas import SearchRequest, SearchResult, VideoMetadata

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_BASE = "https://api.spotify.com/v1"


async def _get_token() -> str:
    credentials = base64.b64encode(
        f"{settings.spotify_client_id}:{settings.spotify_client_secret}".encode()
    ).decode()
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


def _format_duration(ms: int) -> str:
    total_secs = ms // 1000
    h, remainder = divmod(total_secs, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


@activity.defn
async def search_spotify(request: SearchRequest) -> SearchResult:
    """Find a Spotify show by name, then fetch its episodes."""
    token = await _get_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=25) as client:
        # Step 1: Search for shows
        resp = await client.get(f"{SPOTIFY_BASE}/search", headers=headers, params={
            "q": request.query,
            "type": "show",
            "market": "US",
            "limit": 1,
        })
        resp.raise_for_status()
        shows = resp.json().get("shows", {}).get("items", [])

        if not shows:
            activity.logger.warning(f"No Spotify show found for '{request.query}'")
            return SearchResult(channel_name="Unknown")

        show = shows[0]
        show_name = show["name"]
        show_id = show["id"]
        activity.logger.info(f"Found Spotify show: {show_name} ({show_id})")

        # Step 2: Fetch episodes
        resp = await client.get(
            f"{SPOTIFY_BASE}/shows/{show_id}/episodes",
            headers=headers,
            params={"market": "US", "limit": min(request.max_results, 50)},
        )
        resp.raise_for_status()
        episodes = resp.json().get("items", [])

    videos = []
    for ep in episodes:
        duration_ms = ep.get("duration_ms", 0)
        # Filter out short episodes — podcasts are 10+ minutes
        if duration_ms < 600_000:
            continue

        videos.append(VideoMetadata(
            title=ep.get("name", ""),
            url=ep.get("external_urls", {}).get("spotify", ""),
            description=(ep.get("description", "") or "")[:800],
            views=0,
            likes=0,
            comments=0,
            duration=_format_duration(duration_ms),
            date=(ep.get("release_date", "") or "")[:10],
            tags=[],
            chapters=[],
        ))

    activity.logger.info(f"Kept {len(videos)} podcast-length episodes (10+ min) from {len(episodes)} total")
    return SearchResult(channel_name=show_name, videos=videos)
