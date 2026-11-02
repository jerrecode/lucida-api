"""Optional HTTP adapter integration without binding public interfaces."""
import asyncio
import pytest
import httpx
from lucida_api import Config, LucidaClient
from lucida_api.server import create_app


def test_http_api(tmp_path):
    pytest.importorskip("fastapi")
    async def verify():
        app = create_app(LucidaClient(Config(state_dir=tmp_path / "state", output_dir=tmp_path / "media")))
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            version = await http.get("/v1/version")
            assert version.status_code == 200
            assert version.json()["schema"] == 1
            providers = await http.get("/v1/providers")
            assert providers.status_code == 200
            assert any(p["name"] == "sample" for p in providers.json())
            assert (await http.get("/v1/jobs?limit=0")).status_code == 400
            assert (await http.get("/v1/jobs")).json() == []
    asyncio.run(verify())
