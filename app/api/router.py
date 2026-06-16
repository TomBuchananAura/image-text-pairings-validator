import json
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from app.api.schemas import JobStartResponse
from app.core.pipeline import run_pipeline_with_sse
from app.storage.job_store import JobStore

# Initialize the API router
router = APIRouter()
store = JobStore()


def _format_timestamps(job: dict) -> dict:
    """
    Helper function to extract and standardize lifecycle timestamps 
    from a job dictionary for consistent use in all streaming events.
    """
    return {
        "created": job.get("time_created"),
        "processing_started": job.get("time_processing_started"),
        "completed": job.get("time_completed")
    }


@router.post("/process/start/", response_model=JobStartResponse)
async def start_processing(
    images: list[UploadFile] = File(...),
    texts: list[UploadFile] = File(default=[])
):
    """
    Initializes a job pipeline by accepting uploaded image and text files.
    Creates records in the job store and returns initial job IDs for streaming.
    """
    if not images:
        raise HTTPException(400, "At least one image is required.")

    # Create jobs and map file names to generated unique IDs
    job_id_map = await store.create_jobs_for_uploads(images, texts)
    job_ids = list(job_id_map.values())

    return JobStartResponse(
        jobIds=job_ids,
        itemCount=len(job_ids),
        baseNames=list(job_id_map.keys()),
        message=f"{len(job_ids)} job(s) created. Subscribe to SSE streams for each jobId."
    )


@router.get("/process/{job_id}/stream")
async def stream_progress(job_id: str):
    """
    Streams real-time status, progress updates, and results for a specific job ID 
    using Server-Sent Events (SSE).
    """
    job = await store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found or expired.")

    # Helper closure to generate standardized timestamps for the current job status
    get_ts = lambda: _format_timestamps(job)

    # If the job is already finished (complete or failed), stream the final state immediately.
    if job["status"] in ("complete", "failed"):
        async def idle_stream():
            yield f"event: status\ndata: {json.dumps({
                'itemId': job_id, 
                'status': job['status'],
                'timestamps': get_ts()
            })}\n\n"
            return
        return StreamingResponse(idle_stream(), media_type="text/event-stream")

    async def generator():
        try:
            # Check for pre-failure status (e.g., failure during initial upload) 
            # and stream the error event without running the full pipeline.
            if job.get("status") == "failed":
                yield f"event: item_error\ndata: {json.dumps({
                    'itemId': job_id, 
                    'error': job.get('error'),
                    'timestamps': get_ts()
                })}\n\n"
                return

            # Execute the main pipeline and yield all generated SSE events.
            async for event in run_pipeline_with_sse(job_id, store):
                yield event
                
        except Exception as e:
            # Handle critical runtime exceptions during streaming/processing
            yield f"event: item_error\ndata: {json.dumps({
                'itemId': job_id, 
                'error': str(e),
                'timestamps': get_ts()
            })}\n\n"

    # Returns the stream with appropriate headers for long-lived connections
    return StreamingResponse(generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})
