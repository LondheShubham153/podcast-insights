from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    import asyncio

    from activities.analyzer import extract_interests, generate_summary, rank_videos
    from activities.scraper import search_youtube
    from activities.spotify import search_spotify
    from models.schemas import (
        ExtractInterestsRequest,
        RankRequest,
        SearchRequest,
        SummaryRequest,
        WorkflowInput,
        WorkflowStatus,
    )

RETRY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
)


@workflow.defn
class PodcastInsightsWorkflow:
    def __init__(self) -> None:
        self._status = WorkflowStatus("queued")

    @workflow.run
    async def run(self, input: WorkflowInput) -> dict:
        # Step 1: Search provider (YouTube or Spotify)
        search_fn = search_spotify if input.provider == "spotify" else search_youtube
        provider_label = "Spotify" if input.provider == "spotify" else "YouTube"
        self._status = WorkflowStatus("searching", f"Searching {provider_label} for: {input.channel_query}")
        search_result = await workflow.execute_activity(
            search_fn,
            SearchRequest(query=input.channel_query, interests=input.interests, max_results=input.max_videos),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RETRY,
        )

        if not search_result.videos:
            self._status = WorkflowStatus("completed", "No videos found")
            return {
                "channel_name": search_result.channel_name,
                "recommendations": [],
                "summary": f"No videos found for '{input.channel_query}'.",
                "key_insights": [],
                "tone": "unknown",
                "video_count": 0,
                "provider": input.provider,
            }

        videos = search_result.videos

        # Step 2: Extract interests (Gemini LLM, async, 60s)
        self._status = WorkflowStatus("parsing", "Parsing your interests with AI")
        interests = await workflow.execute_activity(
            extract_interests,
            ExtractInterestsRequest(interests=input.interests),
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RETRY,
        )

        # Step 3: Rank + Summarize in parallel (both depend on steps 1+2)
        self._status = WorkflowStatus("ranking_summarizing", f"Ranking & summarizing {len(videos)} videos")

        rank_task = workflow.execute_activity(
            rank_videos,
            RankRequest(
                videos=videos,
                keywords=interests.keywords,
                topics=interests.topics,
            ),
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RETRY,
        )

        summary_task = workflow.execute_activity(
            generate_summary,
            SummaryRequest(
                channel_name=search_result.channel_name,
                videos=videos,
                keywords=interests.keywords,
            ),
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RETRY,
        )

        rank_result, summary_result = await asyncio.gather(rank_task, summary_task)

        recs = rank_result.recommendations
        self._status = WorkflowStatus("completed", f"Found {len(recs)} recommendations")

        return {
            "channel_name": search_result.channel_name,
            "recommendations": [r.model_dump() for r in recs],
            "summary": summary_result.summary,
            "key_insights": summary_result.key_insights,
            "tone": summary_result.tone,
            "video_count": len(videos),
            "provider": input.provider,
        }

    @workflow.query
    def get_status(self) -> WorkflowStatus:
        return self._status
