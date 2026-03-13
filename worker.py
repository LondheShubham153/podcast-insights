import asyncio

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

from activities.analyzer import extract_interests, generate_summary, rank_videos
from activities.scraper import search_youtube
from activities.spotify import search_spotify
from app.config import settings
from workflows.insights import PodcastInsightsWorkflow


async def main():
    client = await Client.connect(
        settings.temporal_host,
        data_converter=pydantic_data_converter,
    )
    worker = Worker(
        client,
        task_queue=settings.task_queue,
        workflows=[PodcastInsightsWorkflow],
        activities=[search_youtube, search_spotify, extract_interests, rank_videos, generate_summary],
    )
    print(f"Worker listening on '{settings.task_queue}' — Ctrl+C to stop")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
