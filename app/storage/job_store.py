#job_store.py
import os
import uuid
import csv
import io
from typing import Dict, Any, List, Optional
from datetime import datetime

class JobStore:
    def __init__(self):
        self.jobs: Dict[str, Dict[str, Any]] = {}

    async def create_jobs_for_uploads(self, img_files: list, text_files: list) -> dict[str, str]:
        def extract_base(f) -> Optional[str]:
            if not f or not f.filename: return None
            base, _ = os.path.splitext(f.filename)
            return base.strip() or None

        img_map: dict[str, bytes] = {}
        for f in img_files:
            base = extract_base(f)
            if base: 
                img_map[base] = await f.read()

        text_map: dict[str, str] = {}
        for f in text_files:
            base = extract_base(f)
            if base:
                content = (await f.read()).decode("utf-8", errors="replace").strip()
                if content: 
                    text_map[base] = content

        all_bases = sorted(set(list(img_map.keys()) + list(text_map.keys())))
        job_id_map = {}

        for base in all_bases:
            job_id = str(uuid.uuid4())
            has_img = base in img_map
            has_text = base in text_map

            status, error_msg = None, None
            context = {"base_name": base, "img_bytes": b"", "parsed_fields": []}

            if not has_img or not has_text:
                status = "failed"
                error_msg = f"Missing {'text' if not has_text else 'image'} file for '{base}'"
            else:
                parsed = self._validate_and_parse_csv(text_map[base])
                if parsed is None:
                    status = "failed"
                    error_msg = f"CSV invalid for '{base}' (expected exactly 1 row with 7 fields)"
                else:
                    status = "pending"
                    context["img_bytes"] = img_map[base]
                    context["parsed_fields"] = parsed

            # 🕒 Lifecycle Timestamps Initialization
            self.jobs[job_id] = {
                "job_id": job_id,
                "base_name": base,
                "status": status if status else "pending",
                "error": error_msg,
                "progress": 0,
                "context": context,
                "time_created": datetime.now().isoformat(),
                "time_processing_started": None,
                "time_completed": None,
            }
            job_id_map[base] = job_id

        return job_id_map

    def _validate_and_parse_csv(self, content: str) -> Optional[List[str]]:
        if not content: return None
        try:
            rows = list(csv.reader(io.StringIO(content)))
            if len(rows) != 1 or len(rows[0]) != 7: return None
            return [field.strip() for field in rows[0]]
        except Exception: 
            return None

    # --- Legacy/Utility methods (kept for pipeline compatibility) ---
    async def create_job(self, job_id: str, img_bytes: List[bytes], parsed_fields: List[List[str]]) -> Dict[str, Any]:
        state = {
            "job_id": job_id, "status": "initializing", "item_count": len(img_bytes),
            "progress": 0, "context": {"img_bytes": img_bytes, "parsed_fields": parsed_fields},
            "time_created": datetime.now().isoformat(),
            "time_processing_started": None,
            "time_completed": None
        }
        self.jobs[job_id] = state
        return state

    async def update_status(self, job_id: str, status: str, progress: int = 0):
        if job := self.jobs.get(job_id):
            job.update({"status": status, "progress": min(progress, 100)})

    async def set_processing_started(self, job_id: str, timestamp: str):
        """Explicitly record when actual processing begins."""
        if job := self.jobs.get(job_id):
            job["time_processing_started"] = timestamp

    async def mark_complete(self, job_id: str):
        if job := self.jobs.get(job_id):
            job.update({
                "status": "complete",
                "progress": 100,
                "time_completed": datetime.now().isoformat()
            })

    async def mark_fail(self, job_id: str, error: str = ""):
        if job := self.jobs.get(job_id):
            job.update({
                "status": "failed",
                "progress": 0,
                "error": error or job.get("error"),
                "time_completed": datetime.now().isoformat()
            })

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self.jobs.get(job_id)

    def get_timestamps(self, job_id: str) -> Dict[str, Optional[str]]:
        """Safely extract the three lifecycle timestamps for frontend consumption."""
        job = self.jobs.get(job_id)
        if not job: 
            return {"created": None, "processing_started": None, "completed": None}
        return {
            "created": job.get("time_created"),
            "processing_started": job.get("time_processing_started"),
            "completed": job.get("time_completed")
        }

    async def cleanup_old_jobs(self, ttl_minutes=60):
        now = datetime.now()
        expired = [jid for jid, job in self.jobs.items()
                   if job["status"] == "complete" and job.get("time_completed") and
                   (now - datetime.fromisoformat(job["time_completed"])).total_seconds() > ttl_minutes * 60]
        for jid in expired:
            del self.jobs[jid]
