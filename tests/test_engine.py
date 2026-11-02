import asyncio
import http.server
import socketserver
import threading
import wave
from pathlib import Path
import pytest
from lucida_api import Config, FileConflict, JobState, LucidaClient, UnsafeSource, safe_filename


def config(tmp_path, **kw):
    return Config(state_dir=tmp_path / "state", output_dir=tmp_path / "music", **kw)


def test_sample_persistence_and_no_clobber(tmp_path):
    client = LucidaClient(config(tmp_path))
    result = asyncio.run(client.acquire("sample://tone"))
    assert result.state == JobState.COMPLETED
    with wave.open(result.destination) as audio:
        assert audio.getnframes() == 8000
    assert LucidaClient(config(tmp_path)).jobs()[0].state == JobState.COMPLETED
    with pytest.raises(FileConflict):
        asyncio.run(client.acquire("sample://tone"))


def test_filename_windows_and_path(tmp_path):
    assert safe_filename("../../CON.mp3").find("/") == -1
    assert safe_filename("AUX") == "file_AUX"
    assert safe_filename("??") == "__"


def test_reject_untrusted(tmp_path):
    client = LucidaClient(config(tmp_path))
    with pytest.raises(UnsafeSource):
        asyncio.run(client.acquire("https://example.com/song.mp3"))
    assert not client.jobs()


def test_recover_interrupted(tmp_path):
    from lucida_api.models import Job
    c = LucidaClient(config(tmp_path))
    c.store.add(Job("abc", "sample://tone", "output", JobState.RUNNING))
    c2 = LucidaClient(config(tmp_path))
    assert c2.store.get("abc").state == JobState.RUNNING
    with pytest.raises(ValueError):
        c2.recover_interrupted()
    assert c2.recover_interrupted(confirm_no_active_workers=True) == 1
    assert c2.store.get("abc").state == JobState.INTERRUPTED


def test_real_local_http_stream(tmp_path):
    media = b"RIFF" + b"a" * 128000
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(media)))
            self.end_headers()
            self.wfile.write(media)
        def log_message(self, *args): pass
    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
    with Server(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = LucidaClient(config(tmp_path, allowed_hosts=("127.0.0.1",), allow_private=True))
            url = f"http://127.0.0.1:{server.server_address[1]}/audio.wav"
            job = asyncio.run(client.acquire(url, "test.wav"))
            assert job.state == JobState.COMPLETED
            assert Path(job.destination).read_bytes() == media
            assert not list((tmp_path / "music").glob("*.part"))
        finally:
            server.shutdown()
            thread.join()


def test_failure_does_not_publish_mismatched_or_unexpected_media(tmp_path):
    class BadServer(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", "5")
            self.end_headers()
            self.wfile.write(b"hello")
        def log_message(self, *args): pass
    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
    with Server(("127.0.0.1", 0), BadServer) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = LucidaClient(config(tmp_path, allowed_hosts=("127.0.0.1",), allow_private=True))
            url = f"http://127.0.0.1:{server.server_address[1]}/bad"
            from lucida_api import TransferError
            with pytest.raises(TransferError, match="MIME"):
                asyncio.run(client.acquire(url, "bad.wav"))
            assert client.jobs()[0].state == JobState.FAILED
            assert not (tmp_path / "music" / "bad.wav").exists()
        finally:
            server.shutdown()
            thread.join()
