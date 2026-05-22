"""data/session.py — Simple file-based conversation persistence.

Saves and loads Streamlit messages and Gemini history to a JSON file
so the user doesn't lose their conversation on page refresh.
"""

import json
from pathlib import Path
from datetime import datetime

# We need to serialize Gemini's Content objects, which are complex Protobuf-backed structures.
import google.generativeai as genai

_SESSION_DIR = Path(__file__).parent.parent / "cache" / "sessions"
_SESSION_FILE = _SESSION_DIR / "latest_session.json"


def _serialize_gemini_history(history: list) -> list[dict]:
    """Convert Gemini Content objects to plain JSON dicts."""
    serialized = []
    for turn in history:
        # A turn is a Content object with a 'role' and a list of 'parts'
        parts_data = []
        for part in turn.parts:
            # We only need to serialize text parts for now, tool calls are complex
            # and we mainly want to preserve the conversational flow.
            if hasattr(part, "text") and part.text:
                 parts_data.append({"text": part.text})
            # To be safe, skip restoring tool call/response parts across sessions.
            # Gemini will just see the text summary of the tool output instead.
            
        if parts_data:
            serialized.append({
                "role": turn.role,
                "parts": parts_data
            })
    return serialized


def _deserialize_gemini_history(data: list[dict]) -> list:
    """Convert plain JSON dicts back to Gemini Content objects."""
    history = []
    for turn_data in data:
        parts = [genai.protos.Part(text=p["text"]) for p in turn_data["parts"]]
        history.append(genai.protos.Content(role=turn_data["role"], parts=parts))
    return history


def save_session(messages: list, gemini_history: list) -> None:
    """Save display messages and serialized Gemini history."""
    _SESSION_DIR.mkdir(parents=True, exist_ok=True)
    
    data = {
        "saved_at": datetime.now().isoformat(),
        "messages": messages,
        "gemini_history": _serialize_gemini_history(gemini_history)
    }
    
    with open(_SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_latest_session() -> tuple[list, list] | None:
    """Load the most recent session if it exists."""
    if not _SESSION_FILE.exists():
        return None
        
    try:
        with open(_SESSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        messages = data.get("messages", [])
        gemini_history = _deserialize_gemini_history(data.get("gemini_history", []))
        return messages, gemini_history
        
    except Exception:
        # If the file is corrupt or format changed, just start fresh
        return None
