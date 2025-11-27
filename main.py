from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime
import httpx
import json
import os
import re

from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

# ============================
# LOAD CONFIG
# ============================
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("MONGODB_DB", "chatbot_db")
OLLAMA_API_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL_NAME = os.getenv("LLM_MODEL", "llama3.1:8b")

# ============================
# MONGO SETUP
# ============================
client = MongoClient(MONGODB_URI, server_api=ServerApi("1"))
db = client[DB_NAME]
sessions_collection = db["sessions"]

try:
    client.admin.command("ping")
    print("✅ MongoDB connected")
except Exception as e:
    print("❌ MongoDB connection failed:", e)

# ============================
# FASTAPI
# ============================
app = FastAPI(title="AI Tutor ChatGPT Clone")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================
# SYSTEM PROMPT
# ============================
SYSTEM_PROMPT = """
You are a helpful, friendly, expert Computer Science tutor.

Rules:
- Use simple language for beginners.
- Explain step-by-step when needed.
- Use headings, bullet points, and clean formatting.
- Include short examples when useful.
- Always keep context from the last messages.
- DO NOT explain grammar unless asked.
- Infer context from earlier conversation.
"""


# ============================
# REQUEST MODELS
# ============================
class MessageRequest(BaseModel):
    text: str
    session_id: str
    expertise_level: Optional[str] = "beginner"


class NewSessionRequest(BaseModel):
    session_id: str


class RenameRequest(BaseModel):
    new_name: str


# ============================
# HELPER FUNCTIONS
# ============================
def clean_response(raw: str) -> str:
    """Clean extra blank lines, normalize."""
    raw = raw.replace("\r\n", "\n")
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def get_conversation_history(session_id: str, limit: int = 12):
    doc = sessions_collection.find_one({"session_id": session_id})
    if not doc:
        return []
    msgs = doc.get("messages", [])
    return msgs[-limit:]


def build_prompt(user_msg: str, history: List[Dict]):
    context = SYSTEM_PROMPT + "\n\n"

    for msg in history:
        role = "User" if msg["role"] == "user" else "Assistant"
        content = msg["content"]
        context += f"{role}: {content}\n"

    final_prompt = (
        f"{context}\nUser: {user_msg}\nAssistant (detailed, structured answer):\n"
    )
    return final_prompt


# ============================
# STREAMING FROM OLLAMA
# ============================
async def stream_llm(prompt: str):
    async with httpx.AsyncClient(timeout=300) as client_http:
        async with client_http.stream(
            "POST",
            OLLAMA_API_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": 0.3, "top_p": 0.9, "num_predict": 2048},
            },
        ) as response:

            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except:
                    continue

                chunk = obj.get("response")
                if chunk:
                    yield chunk


# ============================
# 1️⃣ CREATE SESSION
# ============================
@app.post("/session/new")
async def new_session(req: NewSessionRequest):
    existing = sessions_collection.find_one({"session_id": req.session_id})
    if existing:
        return {"status": "exists"}

    sessions_collection.insert_one(
        {
            "session_id": req.session_id,
            "session_name": "New Chat",
            "messages": [],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        }
    )

    return {"status": "created", "session_id": req.session_id}


# ============================
# 2️⃣ CHAT (STREAMING)
# ============================
@app.post("/chat")
async def chat(req: MessageRequest):

    session_id = req.session_id
    user_text = req.text.strip()

    session = sessions_collection.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    history = get_conversation_history(session_id)
    prompt = build_prompt(user_text, history)

    async def event_stream():
        full_reply = ""

        async for chunk in stream_llm(prompt):
            full_reply += chunk
            yield chunk

        # Save final messages after finishing streaming:
        now = datetime.utcnow()

        messages = session.get("messages", [])
        messages.append({"role": "user", "content": user_text, "timestamp": now.isoformat()})
        messages.append(
            {"role": "assistant", "content": clean_response(full_reply), "timestamp": now.isoformat()}
        )

        sessions_collection.update_one(
            {"session_id": session_id},
            {"$set": {"messages": messages, "updated_at": now}},
        )

        # Auto-name session after first user message
        if session.get("session_name") == "New Chat":
            first_user = next((m for m in messages if m["role"] == "user"), None)
            if first_user:
                title = first_user["content"].split("\n")[0].strip()
                if len(title) > 40:
                    title = title[:37] + "..."
                sessions_collection.update_one(
                    {"session_id": session_id}, {"$set": {"session_name": title}}
                )

    return StreamingResponse(event_stream(), media_type="text/plain")


# ============================
# 3️⃣ GET SESSIONS (SIDEBAR)
# ============================
@app.get("/sessions")
async def get_sessions():
    docs = sessions_collection.find().sort("updated_at", -1)

    result = []
    for doc in docs:
        preview = "New Chat"

        for msg in doc.get("messages", []):
            if msg["role"] == "user":
                preview = msg["content"].split("\n")[0].strip()
                break

        if len(preview) > 35:
            preview = preview[:32] + "..."

        result.append(
            {
                "session_id": doc["session_id"],
                "session_name": doc.get("session_name", "New Chat"),
                "preview": preview,
            }
        )

    return {"sessions": result}


# ============================
# 4️⃣ HISTORY
# ============================
@app.get("/history/{session_id}")
async def get_history(session_id: str):
    doc = sessions_collection.find_one({"session_id": session_id})
    if not doc:
        return {"messages": []}

    msgs = [{"role": m["role"], "content": m["content"]} for m in doc.get("messages", [])]
    return {"messages": msgs}


# ============================
# 5️⃣ DELETE SESSION
# ============================
@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    sessions_collection.delete_one({"session_id": session_id})
    return {"status": "deleted"}


# ============================
# 6️⃣ RENAME SESSION
# ============================
@app.put("/session/{session_id}/rename")
async def rename_session(session_id: str, req: RenameRequest):
    name = req.new_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name cannot be empty")

    sessions_collection.update_one(
        {"session_id": session_id},
        {"$set": {"session_name": name, "updated_at": datetime.utcnow()}},
    )

    return {"status": "renamed"}


# ============================
# DEV SERVER
# ============================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
