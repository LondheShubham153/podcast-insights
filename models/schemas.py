from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field


# --- Temporal I/O (dataclasses for pydantic_data_converter) ---

@dataclass
class SearchRequest:
    query: str
    interests: str = ""
    max_results: int = 10


@dataclass
class VideoMetadata:
    title: str
    url: str
    description: str = ""
    views: int = 0
    likes: int = 0
    comments: int = 0
    duration: str = ""
    date: str = ""
    tags: list[str] = field(default_factory=list)
    chapters: list[str] = field(default_factory=list)


@dataclass
class SearchResult:
    channel_name: str
    videos: list[VideoMetadata] = field(default_factory=list)


@dataclass
class ExtractInterestsRequest:
    interests: str = ""


@dataclass
class RankRequest:
    videos: list[VideoMetadata] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)


@dataclass
class SummaryRequest:
    channel_name: str = ""
    videos: list[VideoMetadata] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


@dataclass
class WorkflowInput:
    channel_query: str
    interests: str
    max_videos: int = 10
    provider: str = "youtube"


@dataclass
class WorkflowStatus:
    phase: str
    detail: str = ""


# --- Pydantic models for Gemini structured output ---

class ExtractedInterests(BaseModel):
    keywords: list[str] = Field(description="Specific keywords from user interests")
    topics: list[str] = Field(description="Broader topic categories")


class VideoRecommendation(BaseModel):
    title: str = Field(description="Video title")
    url: str = Field(description="Video URL")
    score: int = Field(ge=0, le=100, description="Relevance score 0-100")
    why: str = Field(description="One sentence on why this is relevant")
    duration: str = Field(description="Video duration")
    views: int = Field(description="View count")


class RankResult(BaseModel):
    recommendations: list[VideoRecommendation] = Field(description="Ranked video recommendations")


class SummaryResult(BaseModel):
    summary: str = Field(description="Brief overview of the channel's content")
    key_insights: list[str] = Field(description="3-5 key insights about the channel")
    tone: Literal["educational", "entertainment", "news", "tutorial", "mixed"] = Field(
        description="Content tone: educational, entertainment, news, tutorial, or mixed"
    )


# --- API models ---

class AnalyzeRequestAPI(BaseModel):
    channel_query: str = Field(min_length=1)
    interests: str = Field(min_length=1)
    max_videos: int = Field(default=10, ge=3, le=50)
    provider: str = Field(default="youtube", pattern="^(youtube|spotify)$")


class StartResponse(BaseModel):
    workflow_id: str
    status: str = "started"


class StatusResponse(BaseModel):
    workflow_id: str
    phase: str
    detail: str = ""


class WorkflowResult(BaseModel):
    workflow_id: str
    channel_name: str
    recommendations: list[VideoRecommendation]
    summary: str
    key_insights: list[str]
    tone: str
    video_count: int
    provider: str = "youtube"
