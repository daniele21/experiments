import urllib.error

import pytest

from redact_bench.provider import KorgisController, KorgisUnavailableError


def test_korgis_connection_refused_has_actionable_error(monkeypatch):
    def fail(*args, **kwargs):
        raise urllib.error.URLError(ConnectionRefusedError(61, "Connection refused"))

    monkeypatch.setattr("urllib.request.urlopen", fail)

    controller = KorgisController("http://127.0.0.1:1235/v1")
    with pytest.raises(KorgisUnavailableError) as exc_info:
        controller.health()

    message = str(exc_info.value)
    assert "Korgis is not reachable" in message
    assert "http://127.0.0.1:1235/v1" in message
    assert "Connection refused" in message
