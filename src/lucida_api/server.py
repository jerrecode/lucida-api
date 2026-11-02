"""Optional loopback-only FastAPI service for status and controlled demo jobs."""
from __future__ import annotations
import asyncio
import uuid
from contextlib import asynccontextmanager
from .client import LucidaClient


def create_app(client: LucidaClient | None = None):
    from fastapi import FastAPI, HTTPException
    backend = client or LucidaClient()
    running: set[asyncio.Task] = set()
    @asynccontextmanager
    async def lifespan(_app):
        yield
        if running:
            for task in running:
                task.cancel()
            await asyncio.gather(*running, return_exceptions=True)
    app = FastAPI(title="Lucida API", version="0.1.0", lifespan=lifespan)

    @app.get("/v1/version")
    def version():
        return backend.version()

    @app.get("/v1/providers")
    def providers():
        return backend.providers()

    @app.get("/v1/search")
    async def search(q: str, limit: int = 10):
        from .models import LucidaError
        if not q.strip() or len(q) > 256 or not 1 <= limit <= 20:
            raise HTTPException(400, "Invalid search query or result limit")
        try:
            return [item.to_dict() for item in await backend.search(q, limit)]
        except LucidaError as exc:
            raise HTTPException(503, detail={"code": exc.code, "message": str(exc)}) from exc

    @app.get("/v1/jobs")
    def jobs(limit: int = 100):
        if limit < 1 or limit > 1000:
            raise HTTPException(400, "limit out of range")
        return [j.to_dict() for j in backend.jobs(limit)]

    @app.post("/v1/demo", status_code=202)
    async def demo():
        async def perform():
            try:
                await backend.acquire("sample://tone", filename=f"demo-{uuid.uuid4().hex[:12]}.wav")
            except Exception:
                pass  # persisted job contains the error; no hidden success response
        task = asyncio.create_task(perform())
        running.add(task)
        task.add_done_callback(running.discard)
        return {"accepted": True, "note": "Check /v1/jobs for result; submission is not completion"}

    return app


def main():
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=8765)
