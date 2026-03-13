import re

import httpx
from temporalio import activity

from app.config import settings
from models.schemas import SearchRequest, SearchResult, VideoMetadata

YT_BASE = "https://www.googleapis.com/youtube/v3"


def _parse_chapters(description: str) -> list[str]:
    """Extract chapter titles from description timestamps like '0:00 Intro'."""
    chapters = []
    for line in description.split("\n"):
        m = re.match(r"\s*(?:\d{1,2}:)?\d{1,2}:\d{2}\s+(.+)", line.strip())
        if m:
            chapters.append(m.group(1).strip())
    return chapters


def _duration_seconds(iso: str) -> int:
    """Convert ISO 8601 duration (PT1H2M3S) to total seconds."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return 0
    h, mins, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mins * 60 + s


def _parse_duration(iso: str) -> str:
    """Convert ISO 8601 duration (PT1H2M3S) to human readable (1:02:03)."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return iso
    h, mins, s = (int(x) if x else 0 for x in m.groups())
    if h:
        return f"{h}:{mins:02d}:{s:02d}"
    return f"{mins}:{s:02d}"


@activity.defn
async def search_youtube(request: SearchRequest) -> SearchResult:
    """Find channel, then search WITHIN it using user interests for relevance."""
    api_key = settings.youtube_api_key

    async with httpx.AsyncClient(timeout=25) as client:
        # Step 1: Find channel by name (100 units)
        ch_resp = await client.get(f"{YT_BASE}/search", params={
            "part": "snippet",
            "q": request.query,
            "type": "channel",
            "maxResults": 1,
            "key": api_key,
        })
        ch_resp.raise_for_status()
        channels = ch_resp.json().get("items", [])

        if not channels:
            activity.logger.warning(f"No channel found for '{request.query}'")
            return SearchResult(channel_name="Unknown")

        channel_id = channels[0]["id"]["channelId"]
        channel_name = channels[0]["snippet"]["title"]
        activity.logger.info(f"Found channel: {channel_name} ({channel_id})")

        # Step 2: Search WITHIN the channel using interests for relevance (100 units)
        # This gives YouTube-relevance-ranked results from the correct channel
        search_query = request.interests if request.interests else request.query
        vid_resp = await client.get(f"{YT_BASE}/search", params={
            "part": "snippet",
            "q": search_query,
            "type": "video",
            "channelId": channel_id,
            "maxResults": min(request.max_results, 50),
            "order": "relevance",
            "key": api_key,
        })
        vid_resp.raise_for_status()
        vid_items = vid_resp.json().get("items", [])

        if not vid_items:
            activity.logger.warning(f"No relevant videos in {channel_name} for '{search_query}'")
            return SearchResult(channel_name=channel_name)

        video_ids = [
            item["id"]["videoId"]
            for item in vid_items
            if "videoId" in item.get("id", {})
        ]

        if not video_ids:
            return SearchResult(channel_name=channel_name)

        # Step 3: Get full details + tags + topics (1 unit for up to 50 IDs)
        details_resp = await client.get(f"{YT_BASE}/videos", params={
            "part": "snippet,statistics,contentDetails,topicDetails",
            "id": ",".join(video_ids),
            "key": api_key,
        })
        details_resp.raise_for_status()
        details_data = details_resp.json()

    activity.logger.info(f"Fetched {len(video_ids)} relevant videos from {channel_name}")

    videos = []
    for item in details_data.get("items", []):
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})
        raw_duration = content.get("duration", "")
        full_desc = snippet.get("description", "")

        # Filter out short videos — podcasts are 10+ minutes
        if _duration_seconds(raw_duration) < 600:
            continue

        tags = snippet.get("tags", [])[:15]
        topic_urls = item.get("topicDetails", {}).get("topicCategories", [])
        topic_names = [url.rsplit("/", 1)[-1].replace("_", " ") for url in topic_urls]
        all_tags = tags + topic_names
        chapters = _parse_chapters(full_desc)

        videos.append(VideoMetadata(
            title=snippet.get("title", ""),
            url=f"https://www.youtube.com/watch?v={item['id']}",
            description=full_desc[:800],
            views=int(stats.get("viewCount", 0)),
            likes=int(stats.get("likeCount", 0)),
            comments=int(stats.get("commentCount", 0)),
            duration=_parse_duration(raw_duration),
            date=snippet.get("publishedAt", "")[:10],
            tags=all_tags,
            chapters=chapters,
        ))

    activity.logger.info(f"Kept {len(videos)} podcast-length videos (10+ min) from {len(video_ids)} total")
    return SearchResult(channel_name=channel_name, videos=videos)
