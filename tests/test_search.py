import asyncio
import httpx
import pytest
from lucida_api import Config, LucidaClient, CapabilityUnavailable


def test_musicbrainz_metadata_contract(tmp_path):
    seen = []
    def fake(req: httpx.Request):
        seen.append(req)
        assert req.url.host == "musicbrainz.org"
        assert req.url.params["query"] == "test artist"
        assert "LucidaCore/" in req.headers["user-agent"]
        return httpx.Response(200, json={"recordings": [{
            "id": "5e2c", "title": "Example", "score": 91, "length": 180000,
            "artist-credit": [{"name": "Artist One"}, " & ", {"name": "Two"}] }]})
    api = LucidaClient(Config(state_dir=tmp_path / "state", output_dir=tmp_path / "output"))
    async def exercise():
        return await api.search("test artist", transport=httpx.MockTransport(fake))
    result = asyncio.run(exercise())
    assert result[0].to_dict() == {
        "id": "5e2c", "title": "Example", "artist": "Artist One & Two", "provider": "musicbrainz",
        "duration_ms": 180000, "score": 91}
    assert len(seen) == 1
    assert not any(p["name"] == "musicbrainz" and p["acquisition"] for p in api.providers())


def test_search_validation_and_error(tmp_path):
    api = LucidaClient(Config(state_dir=tmp_path / "state", output_dir=tmp_path / "output"))
    with pytest.raises(ValueError):
        asyncio.run(api.search(" "))
    def fake(req):
        return httpx.Response(503, text="unavailable")
    with pytest.raises(CapabilityUnavailable, match="503"):
        asyncio.run(api.search("anything", transport=httpx.MockTransport(fake)))
