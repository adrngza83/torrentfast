"""Engine tests: upload cap from line speed and queue priority."""
import types

import pytest

import torrentfast_web as web
from torrentfast import upload_limit_bytes

A = "magnet:?xt=urn:btih:08ada5a7a6183aae1e09d831df6748d566095a10&dn=A"
B = "magnet:?xt=urn:btih:dd8255ecdc7ca55fb0bbf81323d87062db1f6d1c&dn=B"
C = "magnet:?xt=urn:btih:a88fda5954e89178c372716a6a78b8180ed4dad3&dn=C"


def test_upload_cap_math():
    assert upload_limit_bytes(300, 10) == 3_750_000      # 30 Mbps
    assert upload_limit_bytes(90, 10) == 1_125_000       # 9 Mbps
    assert upload_limit_bytes(300, 100) == 0             # unlimited


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "data_dir", lambda: _mk(tmp_path / "state"))
    e = web.Engine(types.SimpleNamespace(out=str(tmp_path / "dl"), port=0, max_down=0, max_up=0, lan=False))
    yield e
    e.ses.pause()


def _mk(p):
    for sub in ("", "resume", "torrents", "http"):
        (p / sub).mkdir(parents=True, exist_ok=True)
    return str(p)


def test_engine_applies_upload_cap(engine):
    assert engine.ses.get_settings()["upload_rate_limit"] == 3_750_000
    assert engine.ses.get_settings()["download_rate_limit"] == 0
    engine.save_settings(line_mbps=90)
    assert engine.ses.get_settings()["upload_rate_limit"] == 1_125_000


def test_download_first_beats_smart_queue(engine):
    ids = [engine.add(m) for m in (A, B, C)]
    engine.action(ids[2], "top")
    engine.rank_queue()
    order = {i["ih"]: i["queue"] for i in engine.status()["items"]}
    assert order[ids[2]] == 0


def test_rejects_bad_mirror(engine):
    ih = engine.add(A)
    with pytest.raises(ValueError):
        engine.action(ih, "mirror", "ftp://nope")
    engine.action(ih, "mirror", "https://mirror.example.com/file")
    assert [i for i in engine.status()["items"] if i["ih"] == ih][0]["mirrors"] == 1
