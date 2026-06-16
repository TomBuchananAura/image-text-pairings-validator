import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any
from PIL import Image
from io import BytesIO
from datetime import datetime

# Assuming these imports are available in the project structure
from app.core.preprocessor import preprocess_image
from app.core.ocr_processor import extract_text
from app.core.validator import validate_similarity
from app.storage.job_store import JobStore

logger = logging.getLogger("pipeline")


def _sse(event: str, data: Dict[str, Any]) -> str:
    """
    Formats a dictionary of status data into a standard Server-Sent Event (SSE) message string.

    Args:
        event: The event type identifier (e.g., 'status', 'complete').
        data: A dictionary containing the payload data for the event.

    Returns:
        A formatted SSE message string.
    """
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# Global lock to ensure that only one instance of the pipeline executes critical steps 
# (like marking start/finish) for a given job ID at any time.
_SERIAL_LOCK = asyncio.Lock()

async def run_pipeline_with_sse(job_id: str, store: JobStore) -> AsyncGenerator[str, None]:
    """
    Manages the complete lifecycle of image processing, from acquisition to validation.

    This asynchronous generator yields Server-Sent Event (SSE) messages throughout 
    the process, allowing a consuming client (like a web front-end) to track 
    the job's status in real time.

    The pipeline stages are: Status Check -> Preprocessing -> OCR Extraction -> Validation.

    Args:
        job_id: The unique identifier of the job being processed.
        store: An interface object used to read and update job metadata (status, timestamps).

    Yields:
        str: A formatted SSE message string detailing the current status or final result.

    Raises:
        RuntimeError: If the specified job_id is not found in the store.
    """
    logger.info(f"Pipeline started for Job ID: {job_id}")
    job = await store.get_job(job_id)
    if not job:
        raise RuntimeError(f"Job {job_id} not found in store.")

    # Check if the job has already reached a terminal state (complete or failed).
    final_status = job.get("status")
    if final_status in ("complete", "failed"):
        yield _sse("status", {
            "itemId": job_id, 
            "status": final_status, 
            "timestamps": store.get_timestamps(job_id)
        })
        return

    # Initial status update: Job is queued.
    yield _sse("status", {
        "itemId": job_id,
        "status": "queued",
        "timestamps": store.get_timestamps(job_id)
    })
    
    async with _SERIAL_LOCK:
        # Update status to processing start and yield event.
        ts_start = datetime.now().isoformat()
        await store.set_processing_started(job_id, ts_start)
        
        yield _sse("status", {
            "itemId": job_id,
            "status": "processing",
            "timestamps": store.get_timestamps(job_id)
        })

        # Re-fetch job context to ensure consistency within the lock block
        job = await store.get_job(job_id)
        if not job:
            raise RuntimeError(f"Job {job_id} not found in store during processing.")

        context = job.get("context", {})
        img_bytes = context.get("img_bytes")
        target_fields = context.get("parsed_fields")

        # --- Input Validation Checks ---
        if not isinstance(img_bytes, (bytes, bytearray)):
            err = f"Invalid img_bytes type: {type(img_bytes).__name__}"
            logger.error(f"[JOB:{job_id}] Critical Failure: Invalid image bytes.")
            await store.mark_fail(job_id, err)
            yield _sse("item_error", {"itemId": job_id, "error": err, "timestamps": store.get_timestamps(job_id)})
            return

        if not isinstance(target_fields, list) or len(target_fields) != 7:
            err = f"Invalid fields array: expected 7, got {len(target_fields)}"
            logger.error(f"[JOB:{job_id}] Critical Failure: Invalid target field count.")
            await store.mark_fail(job_id, err)
            yield _sse("item_error", {"itemId": job_id, "error": err, "timestamps": store.get_timestamps(job_id)})
            return

        if job.get("status") == "failed":
            logger.warning(f"[JOB:{job_id}] Processing skipped due to pre-existing failure status.")
            yield _sse("item_error", {
                "itemId": job_id, 
                "error": job.get("error"), 
                "timestamps": store.get_timestamps(job_id)
            })
            return

        try:
            # STEP 1: Preprocessing validation and notification
            logger.info(f"[JOB:{job_id}] Step 1/5: Validating image size.")
            yield _sse("status", {"itemId": job_id, "status": "preprocessing", "timestamps": store.get_timestamps(job_id)})
            await asyncio.sleep(0)  

            # STEP 2: PIL loading and standardizing the image format
            logger.info(f"[JOB:{job_id}] Step 2/5: Loading and enhancing image.")
            pil = Image.open(BytesIO(img_bytes)).convert("RGB")
            proc = preprocess_image(pil)
            await asyncio.sleep(0)  

            # STEP 3: OCR extraction
            logger.info(f"[JOB:{job_id}] Step 3/5: Running OCR text extraction.")
            yield _sse("status", {"itemId": job_id, "status": "ocr", "timestamps": store.get_timestamps(job_id)})
            extracted_text = extract_text(proc)
            await asyncio.sleep(0)

            # STEP 4: Semantic Validation
            logger.info(f"[JOB:{job_id}] Step 4/5: Running semantic validation against targets.")
            yield _sse("status", {"itemId": job_id, "status": "validating", "timestamps": store.get_timestamps(job_id)})
            validation_result = validate_similarity(extracted_text, target_fields)
            await asyncio.sleep(0)

            # STEP 5: Success and finalization
            logger.info(f"[JOB:{job_id}] Step 5/5: Pipeline successfully completed.")
            await store.mark_complete(job_id)
            
            yield _sse("complete", {
                "itemId": job_id, 
                "status": "success", 
                "result": validation_result,
                "timestamps": store.get_timestamps(job_id)
            })

        except Exception as e:
            # Catch any exception and handle failure reporting to the store/client
            logger.error(f"[JOB:{job_id}] Pipeline failed during execution: {e}", exc_info=True)
            await store.mark_fail(job_id, str(e))
            yield _sse("item_error", {
                "itemId": job_id, 
                "error": str(e),
                "timestamps": store.get_timestamps(job_id)
            })
