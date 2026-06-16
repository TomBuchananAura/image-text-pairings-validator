from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class JobTimestamps(BaseModel):
    """Defines standardized lifecycle timestamps for a job."""
    created: Optional[str] = None
    processing_started: Optional[str] = None
    completed: Optional[str] = None


class JobStartResponse(BaseModel):
    """Payload structure returned upon successfully starting a job process."""
    jobIds: List[str]           # List of IDs for all submitted jobs (success or failed).
    itemCount: int              # Total number of items processed in this job.
    baseNames: List[str]        # Readable identifiers for the submitted files, used for frontend mapping.
    message: str = "Jobs created. Subscribe to SSE streams using the returned jobIds."


class ProgressUpdate(BaseModel):
    """Schema used for streaming progress updates (e.g., upload, OCR, validation)."""
    itemId: str
    progress: int = Field(ge=0, le=100)

    def to_sse(self, event_type: str) -> str:
        """Formats the update data into a Server-Sent Events (SSE) string."""
        return f"event: {event_type}\ndata: {self.model_dump_json()}\n\n"


class MetricsUpdate(BaseModel):
    """Schema used for streaming detailed metrics updates during processing."""
    itemId: str
    metrics: Dict[str, Any]

    def to_sse(self) -> str:
        """Formats the metrics data into a Server-Sent Events (SSE) string."""
        return f"event: metrics_update\ndata: {self.model_dump_json()}\n\n"


class JobCompletion(BaseModel):
    """Schema representing the final, successful results of a job pipeline run."""
    results: Dict[str, Any]  # A dictionary mapping base names to their processing results.

    def to_sse(self) -> str:
        """Formats the completion data into an SSE string."""
        return f"event: job_complete\ndata: {self.model_dump_json()}\n\n"


class JobFailure(BaseModel):
    """Schema representing a critical failure event during pipeline execution."""
    error: str

    def to_sse(self) -> str:
        """Formats the error data into an SSE string."""
        return f"event: job_error\ndata: {self.model_dump_json()}\n\n"
