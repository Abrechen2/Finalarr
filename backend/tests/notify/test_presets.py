import pytest

from finalarr.notify.presets import PresetError, build_url, describe

TOKEN = "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"


@pytest.mark.parametrize(
    ("kind", "fields", "url"),
    [
        ("telegram", {"bot_token": TOKEN, "chat_id": "-100123"}, f"tgram://{TOKEN}/-100123"),
        ("telegram", {"bot_token": TOKEN, "chat_id": "@channel"}, f"tgram://{TOKEN}/@channel"),
        (
            "discord",
            {"webhook_url": "https://discord.com/api/webhooks/123/abc-DEF_9"},
            "discord://123/abc-DEF_9",
        ),
        (
            "pushover",
            {"user_key": "u" * 30, "app_token": "a" * 30},
            f"pover://{'u' * 30}@{'a' * 30}",
        ),
        ("webhook", {"url": "https://example.org/hook?x=1"}, "jsons://example.org/hook?x=1"),
        ("webhook", {"url": "http://10.0.0.5:8080/in"}, "json://10.0.0.5:8080/in"),
        ("apprise", {"url": "ntfy://topic"}, "ntfy://topic"),
    ],
)
def test_presets_build_apprise_urls(kind, fields, url):
    assert build_url(kind, fields) == url


@pytest.mark.parametrize(
    ("kind", "fields", "field"),
    [
        ("telegram", {"bot_token": "nope", "chat_id": "1"}, "bot_token"),
        ("telegram", {"bot_token": TOKEN, "chat_id": "abc"}, "chat_id"),
        ("discord", {"webhook_url": "https://evil.example/api/webhooks/1/x"}, "webhook_url"),
        ("pushover", {"user_key": "short", "app_token": "a" * 30}, "user_key"),
        ("webhook", {"url": "ftp://x"}, "url"),
        ("apprise", {"url": "nonsense://x"}, "url"),
        ("carrier-pigeon", {}, "kind"),
    ],
)
def test_invalid_fields_name_the_field(kind, fields, field):
    with pytest.raises(PresetError) as info:
        build_url(kind, fields)
    assert info.value.field == field


def test_describe_never_shows_secrets():
    assert describe(f"tgram://{TOKEN}/-100123") == "tgram://***"
    assert describe("jsons://example.org/hook") == "jsons://***"
