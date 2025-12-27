"""Tests for solaredge2mqtt.__main__ entrypoint."""

import runpy
import sys

import solaredge2mqtt.service as service_module


def test_main_invokes_service_run(monkeypatch):
    sys.modules.pop("solaredge2mqtt.__main__", None)
    called = {"count": 0}

    def fake_run():
        called["count"] += 1

    monkeypatch.setattr(service_module, "run", fake_run)

    runpy.run_module("solaredge2mqtt.__main__", run_name="__main__")

    assert called["count"] == 1