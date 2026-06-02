"""Tests for ChatSession.record_turn."""

from __future__ import annotations

from imagecb.retrieval.session import ChatSession


def test_record_turn_stores_assistant_message():
    session = ChatSession()
    session.record_turn("find charts", "I found 3 charts. Try narrowing to Q3.")
    assert len(session.history) == 1
    user, assistant = session.history[0]
    assert user == "find charts"
    assert "3 charts" in assistant
