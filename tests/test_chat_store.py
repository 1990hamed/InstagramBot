"""Tests for the Telegram chat-id persistence helpers."""

import json

from instabot.telegram_report import chat_store


def test_save_then_load_round_trips(tmp_path, monkeypatch):
    chat_file = tmp_path / "telegram_chat.json"
    monkeypatch.setattr(chat_store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(chat_store, "CHAT_FILE", chat_file)

    chat_store.save_chat_id(148998445)

    assert json.loads(chat_file.read_text(encoding="utf-8")) == {
        "chat_id": "148998445"
    }
    # chat ids are persisted (and returned) as strings.
    assert chat_store.load_chat_id() == "148998445"


def test_load_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(chat_store, "CHAT_FILE", tmp_path / "missing.json")

    assert chat_store.load_chat_id() is None
