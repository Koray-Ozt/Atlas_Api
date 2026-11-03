import json
import logging

from app.logging import JsonFormatter, request_id_var


def _record(**extra) -> logging.LogRecord:
    record = logging.LogRecord("atlas", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    record.__dict__.update(extra)
    return record


def test_formatter_emits_json_with_extra_fields():
    line = JsonFormatter().format(_record(status=200))
    data = json.loads(line)
    assert data["message"] == "hello world"
    assert data["level"] == "INFO"
    assert data["status"] == 200
    assert "request_id" not in data


def test_formatter_includes_request_id_when_set():
    token = request_id_var.set("abc123")
    try:
        data = json.loads(JsonFormatter().format(_record()))
    finally:
        request_id_var.reset(token)
    assert data["request_id"] == "abc123"
