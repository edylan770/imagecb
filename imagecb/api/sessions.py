"""In-memory chat session store."""

from __future__ import annotations

import uuid
from threading import Lock
from typing import Dict

from imagecb.retrieval.session import ChatSession

_lock = Lock()
_sessions: Dict[str, ChatSession] = {}


def create_session() -> tuple[str, ChatSession]:
    session_id = str(uuid.uuid4())
    session = ChatSession()
    with _lock:
        _sessions[session_id] = session
    return session_id, session


def get_session(session_id: str) -> ChatSession | None:
    with _lock:
        return _sessions.get(session_id)


def get_or_create_session(session_id: str | None) -> tuple[str, ChatSession]:
    if session_id:
        session = get_session(session_id)
        if session is not None:
            return session_id, session
    return create_session()


def reset_session(session_id: str) -> ChatSession | None:
    session = get_session(session_id)
    if session is None:
        return None
    session.reset()
    return session
