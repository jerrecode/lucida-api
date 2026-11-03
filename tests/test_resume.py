"""Deterministic local HTTP Range / strong-ETag resume contract."""
import asyncio
import http.server
import socket
import threading
from pathlib import Path
import pytest
from lucida_api import Config, JobState, LucidaClient, TransferError
from lucida_api.checkpoint import manifest_path, strong_etag

DATA = b"RIFF" + (b"safe-license-test-data" * 50000)
ETAG = '"v1-strong"'


def serve(mode):
    seen = []
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            rng = self.headers.get("Range")
            ir = self.headers.get("If-Range")
            seen.append((rng, ir))
            if not rng:
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("ETag", ETAG)
                self.send_header("Content-Length", str(len(DATA)))
                self.end_headers()
                self.wfile.write(DATA[:len(DATA)//2])
                self.wfile.flush()
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
            else:
                offset = int(rng.split("=")[1].split("-")[0])
                assert ir == ETAG
                if mode == "changed":
                    self.send_response(200)
                    self.send_header("ETag", '"v2-new"')
                    self.send_header("Content-Type", "audio/wav")
                    self.send_header("Content-Length", str(len(DATA)))
                    self.end_headers()
                    self.wfile.write(DATA)
                else:
                    self.send_response(206)
                    self.send_header("Content-Type", "audio/wav")
                    self.send_header("ETag", ETAG)
                    self.send_header("Content-Range", f"bytes {offset}-{len(DATA)-1}/{len(DATA)}")
                    self.send_header("Content-Length", str(len(DATA)-offset))
                    self.end_headers()
                    self.wfile.write(DATA[offset:])
        def log_message(self, *args):
            pass
    class Server(http.server.ThreadingHTTPServer):
        allow_reuse_address = True
    server = Server(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, seen


@pytest.mark.parametrize("mode", ["unchanged", "changed"])
def test_resume_strong_etag(tmp_path, mode):
    server, thread, seen = serve(mode)
    try:
        cfg = Config(state_dir=tmp_path / "state", output_dir=tmp_path / "music",
                     allowed_hosts=("127.0.0.1",), allow_private=True)
        client = LucidaClient(cfg)
        url = f"http://127.0.0.1:{server.server_address[1]}/test.wav"
        with pytest.raises(TransferError):
            asyncio.run(client.acquire(url, "test.wav"))
        job = client.jobs()[0]
        assert job.state == JobState.FAILED
        partial = cfg.output_dir / f".test.wav.{job.id}.part"
        size = partial.stat().st_size
        assert 0 < size < len(DATA)
        assert manifest_path(partial).is_file()
        client2 = LucidaClient(cfg)
        if mode == "changed":
            with pytest.raises(TransferError, match="resumption refused"):
                asyncio.run(client2.resume(job.id))
            assert partial.stat().st_size == size
            assert not (cfg.output_dir / "test.wav").exists()
        else:
            finished = asyncio.run(client2.resume(job.id))
            assert finished.state == JobState.COMPLETED
            assert Path(finished.destination).read_bytes() == DATA
            assert not partial.exists() and not manifest_path(partial).exists()
        assert seen[1][0] == f"bytes={size}-"
    finally:
        server.shutdown()
        thread.join()


def test_etag_validation():
    assert strong_etag('"abc"') == '"abc"'
    assert strong_etag('W/"abc"') is None
    assert strong_etag("invalid") is None
    assert strong_etag('"control\\n"') is not None  # escaped two-char string is legal
    assert strong_etag('"control\n"') is None
