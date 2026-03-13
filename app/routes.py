import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request
from temporalio.client import WorkflowFailureError
from temporalio.service import RPCError

from models.schemas import (
    AnalyzeRequestAPI,
    StartResponse,
    StatusResponse,
    WorkflowInput,
    WorkflowResult,
    WorkflowStatus,
)
from workflows.insights import PodcastInsightsWorkflow

router = APIRouter(prefix="/api", tags=["insights"])


@router.post("/analyze", response_model=StartResponse)
async def start_analysis(request: Request, body: AnalyzeRequestAPI) -> StartResponse:
    client = request.app.state.temporal_client
    wf_id = f"insights-{uuid.uuid4().hex[:8]}"

    await client.start_workflow(
        PodcastInsightsWorkflow.run,
        WorkflowInput(
            channel_query=body.channel_query,
            interests=body.interests,
            max_videos=body.max_videos,
            provider=body.provider,
        ),
        id=wf_id,
        task_queue=request.app.state.task_queue,
        execution_timeout=timedelta(minutes=5),
    )
    return StartResponse(workflow_id=wf_id)


@router.get("/status/{workflow_id}", response_model=StatusResponse)
async def get_status(request: Request, workflow_id: str) -> StatusResponse:
    client = request.app.state.temporal_client
    handle = client.get_workflow_handle(workflow_id)
    try:
        status: WorkflowStatus = await handle.query(PodcastInsightsWorkflow.get_status)
        return StatusResponse(
            workflow_id=workflow_id,
            phase=status.phase,
            detail=status.detail,
        )
    except RPCError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/result/{workflow_id}", response_model=WorkflowResult)
async def get_result(request: Request, workflow_id: str) -> WorkflowResult:
    client = request.app.state.temporal_client
    handle = client.get_workflow_handle(workflow_id)
    try:
        result = await handle.result()
        return WorkflowResult(workflow_id=workflow_id, **result)
    except WorkflowFailureError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RPCError as e:
        raise HTTPException(status_code=404, detail=str(e))
