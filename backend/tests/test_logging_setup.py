import logging

from finalarr.logging_setup import RedactingFilter, configure_logging


def redact(message, *args):
    record = logging.LogRecord("x", logging.INFO, __file__, 1, message, args, None)
    RedactingFilter().filter(record)
    return record.getMessage()


def test_webhook_tokens_are_redacted():
    token = "a" * 64
    assert token not in redact("POST /webhook/sonarr/%s 202", token)


def test_api_keys_and_apprise_urls_are_redacted():
    out = redact("call with apikey=abc123 and X-Api-Key: zzz to tgram://123456:ABCdef/42")
    assert "abc123" not in out
    assert "zzz" not in out
    assert "ABCdef" not in out
    assert "tgram://***" in out


def test_plain_messages_pass_unchanged():
    assert redact("Reconcile of instance %s done", 3) == "Reconcile of instance 3 done"


def test_configure_logging_writes_a_rotating_file(tmp_path):
    configure_logging("INFO", tmp_path)
    logging.getLogger("finalarr.test").warning("hello apikey=secret")
    for handler in logging.getLogger().handlers:
        handler.flush()
    content = (tmp_path / "finalarr.log").read_text()
    assert "hello" in content
    assert "secret" not in content
    configure_logging("INFO", tmp_path)
    assert sum(1 for h in logging.getLogger().handlers if getattr(h, "finalarr", False)) == 2


def test_tracebacks_are_redacted_too(tmp_path):
    configure_logging("INFO", tmp_path)
    try:
        raise RuntimeError("failed with apikey=tracesecret on tgram://123:ABC/9")
    except RuntimeError:
        logging.getLogger("finalarr.test").exception("boom")
    for handler in logging.getLogger().handlers:
        handler.flush()
    content = (tmp_path / "finalarr.log").read_text()
    assert "Traceback" in content
    assert "tracesecret" not in content
    assert "ABC" not in content


def test_scheduler_skip_warnings_are_quiet(tmp_path):
    configure_logging("INFO", tmp_path)
    assert logging.getLogger("apscheduler").getEffectiveLevel() == logging.ERROR
