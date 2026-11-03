"""Optional loopback-only FastAPI service; controls in-process SDK jobs."""
from __future__ import annotations
import uuid
from contextlib import asynccontextmanager
from .client import LucidaClient
from .models import JobState, LucidaError


def create_app(client: LucidaClient | None = None):
    from fastapi import FastAPI, HTTPException
    backend = client or LucidaClient()

    @asynccontextmanager
    async def lifespan(_app):
        yield
        await backend.shutdown()

    app = FastAPI(title="Lucida API", version="0.1.0", lifespan=lifespan)

    @app.get("/v1/version")
    def version():
        return backend.version()

    @app.get("/v1/providers")
    def providers():
        return backend.providers()

    @app.get("/v1/search")
    async def search(q: str, limit: int = 10):
        if not q.strip() or len(q) > 256 or not 1 <= limit <= 20:
            raise HTTPException(400, "Invalid search query or result limit")
        try:
            return [item.to_dict() for item in await backend.search(q, limit)]
        except LucidaError as exc:
            raise HTTPException(503, detail={"code": exc.code, "message": str(exc)}) from exc

    @app.get("/v1/jobs")
    def jobs(limit: int = 100):
        if not 1 <= limit <= 1000:
            raise HTTPException(400, "limit out of range")
        return [j.to_dict() for j in backend.jobs(limit)]

    @app.get("/v1/jobs/{job_id}")
    def job(job_id: str):
        result = backend.store.get(job_id)
        if result is None:
            raise HTTPException(404, "Unknown job")
        return result.to_dict()

    @app.post("/v1/jobs/{job_id}/cancel")
    async def cancel(job_id: str):
        if backend.store.get(job_id) is None:
            raise HTTPException(404, "Unknown job")
        if not await backend.cancel(job_id):
            raise HTTPException(409, "Job is not active in this server process")
        return backend.store.get(job_id).to_dict()

    @app.post("/v1/demo", status_code=202)
    async def demo():
        try:
            identifier = await backend.submit(
                "sample://tone", filename=f"demo-{uuid.uuid4().hex[:12]}.wav")
        except (LucidaError, OSError) as exc:
            raise HTTPException(409, detail={"code": getattr(exc, "code", "io_error"),
                                             "message": str(exc)}) from exc
        return {"job_id": identifier, "state": JobState.QUEUED,
                "note": "Submission accepted, not a completion guarantee"}

    return app


def main():
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=8765)
