"""Background job control and journal tests using no external network."""
import asyncio
import wave
import pytest
import httpx
from lucida_api import Config, JobState, LucidaClient
from lucida_api.server import create_app


def api(tmp_path, maximum=1):
    return LucidaClient(Config(state_dir=tmp_path / "state", output_dir=tmp_path / "output",
                               max_concurrent=maximum))


def test_submit_wait_and_unknown_job(tmp_path):
    async def exercise():
        client = api(tmp_path)
        ids = [await client.submit("sample://tone", f"test-{i}.wav") for i in range(4)]
        assert all(client.store.get(id).state in (JobState.QUEUED, JobState.RUNNING, JobState.COMPLETED)
                   for id in ids)
        results = await asyncio.gather(*(client.wait(id) for id in ids))
        assert all(result.state == JobState.COMPLETED for result in results)
        assert len({item.destination for item in results}) == 4
        assert not await client.cancel(ids[0])
        with pytest.raises(ValueError, match="Unknown job"):
            await client.wait("missing")
        for item in results:
            with wave.open(item.destination) as src:
                assert src.getnframes() == 8000
    asyncio.run(exercise())


def test_cancel_queued_job_and_retry(tmp_path):
    async def exercise():
        client = api(tmp_path)
        await client._limit.acquire()  # deterministic queued cancellation with full worker capacity
        try:
            identifier = await client.submit("sample://tone", "cancel-me.wav")
            await asyncio.sleep(0)  # enter semaphore wait
            assert await client.cancel(identifier)
            assert client.store.get(identifier).state == JobState.CANCELLED
            assert not (tmp_path / "output" / "cancel-me.wav").exists()
        finally:
            client._limit.release()
        new = await client.retry(identifier)
        assert new.id != identifier
        assert new.state == JobState.COMPLETED
        with pytest.raises(ValueError):
            await client.retry(new.id)
    asyncio.run(exercise())


def test_service_lifecycle(tmp_path):
    async def exercise():
        backend = api(tmp_path)
        transport = httpx.ASGITransport(app=create_app(backend))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            response = await http.post("/v1/demo")
            assert response.status_code == 202
            job_id = response.json()["job_id"]
            initial = await http.get(f"/v1/jobs/{job_id}")
            assert initial.status_code == 200
            result = await backend.wait(job_id)
            assert result.state == JobState.COMPLETED
            assert (await http.post(f"/v1/jobs/{job_id}/cancel")).status_code == 409
            assert (await http.get("/v1/jobs/does-not-exist")).status_code == 404
        await backend.shutdown()
    asyncio.run(exercise())
