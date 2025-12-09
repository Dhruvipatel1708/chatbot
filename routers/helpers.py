import re
from config import SYSTEM_PROMPT, sessions_collection

def clean_response(raw: str) -> str:
    raw = raw.replace("\r\n", "\n")
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()

def get_conversation_history(session_id: str, limit: int = 12):
    doc = sessions_collection.find_one({"session_id": session_id})
    if not doc:
        return []
    msgs = doc.get("messages", [])
    return msgs[-limit:]

def build_prompt(user_msg: str, history):
    context = SYSTEM_PROMPT + "\n\n"
    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        context += f"{role}: {msg['content']}\n"
    return f"{context}\nUser: {user_msg}\nAssistant:"
