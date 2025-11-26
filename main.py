from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from typing import Dict, List, Optional
import re

from pymongo import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
import os
from datetime import datetime

print("==============")
load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGODB_URI, server_api=ServerApi('1'))
db = client[os.getenv("MONGODB_DB", "chatbot_db")]
conversations = db["conversations"]
print("==============")

# Test DB connection
try:
    client.admin.command('ping')
    print("✅ MongoDB connected")
except Exception as e:
    print("❌ MongoDB error:", e)


app = FastAPI(title="FAST CS Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:1b"

SYSTEM_PROMPT = """
You are a Computer Science tutor. Respond in clean, well-formatted text.
"""


class Message(BaseModel):
    text: str
    session_id: str
    conversation_history: List[Dict[str, str]] = []
    expertise_level: Optional[str] = "intermediate"


class RenameRequest(BaseModel):
    new_name: str


# ---------------------------------------
# CLEANING FUNCTION
# ---------------------------------------
def clean_response(raw: str) -> str:
    raw = re.sub(r"[*_`#~>\[\]]", "", raw)
    raw = raw.replace("+", "\n- ").replace("•", "\n- ")
    raw = raw.replace("–", "\n- ").replace("—", "\n- ")
    raw = re.sub(r"\s*-\s*", "\n- ", raw)
    raw = re.sub(r"\n+", "\n", raw)
    raw = raw.strip()
    return raw[:500] + "..." if len(raw) > 500 else raw


# ---------------------------------------
# GENERATE BOT RESPONSE
# ---------------------------------------
async def generate_response(prompt: str, conversation_history, expertise_level):

    try:
        context = SYSTEM_PROMPT + "\n\n"

        for msg in conversation_history[-2:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            context += f"{role}: {msg['content']}\n"

        final_prompt = f"""
{context}

### User Question:
{prompt}

### Assistant Answer:
"""

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                OLLAMA_API_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": final_prompt,
                    "stream": False,
                    "options": {"temperature": 0.2},
                },
            )

        data = response.json()
        raw = data.get("response") or str(data)
        return clean_response(raw)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------
# 1️⃣ CREATE NEW SESSION
# ---------------------------------------
@app.post("/session/new")
async def new_session(data: dict):
    session_id = data.get("session_id")

    conversations.insert_one({
        "session_id": session_id,
        "session_name": "New Chat",
        "timestamp": datetime.utcnow(),
        "user_message": None,
        "bot_response": None
    })

    return {"status": "created", "session_id": session_id}


# ---------------------------------------
# 2️⃣ CHAT ENDPOINT (save chat)
# ---------------------------------------
@app.post("/chat")
async def chat(message: Message):

    reply = await generate_response(
        message.text,
        message.conversation_history,
        message.expertise_level
    )

    conversations.insert_one({
        "session_id": message.session_id,
        "user_message": message.text,
        "bot_response": reply,
        "timestamp": datetime.utcnow()
    })

    return {"response": reply}


# ---------------------------------------
# 3️⃣ GET ALL SESSIONS (sidebar)
# ---------------------------------------
@app.get("/sessions")
async def get_sessions():
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": "$session_id",
            "latest_timestamp": {"$first": "$timestamp"},
            "latest_user": {"$first": "$user_message"},
            "name": {"$first": "$session_name"},
        }},
        {"$sort": {"latest_timestamp": -1}},
    ]

    sessions = []
    for s in conversations.aggregate(pipeline):

        preview = s.get("latest_user") or "New Chat"
        if preview and len(preview) > 35:
            preview = preview[:32] + "..."

        sessions.append({
            "session_id": s["_id"],
            "preview": preview,
            "session_name": s.get("name") or preview
        })

    return {"sessions": sessions}


# ---------------------------------------
# 4️⃣ LOAD CHAT HISTORY
# ---------------------------------------
@app.get("/history/{session_id}")
async def get_history(session_id: str):
    cursor = conversations.find({"session_id": session_id}).sort("timestamp", 1)

    msgs = []
    for c in cursor:
        if c.get("user_message"):
            msgs.append({"role": "user", "content": c["user_message"]})
        if c.get("bot_response"):
            msgs.append({"role": "bot", "content": c["bot_response"]})

    return {"messages": msgs}


# ---------------------------------------
# 5️⃣ DELETE SESSION
# ---------------------------------------
@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    conversations.delete_many({"session_id": session_id})
    return {"status": "deleted"}


# ---------------------------------------
# 6️⃣ RENAME SESSION
# ---------------------------------------
@app.put("/session/{session_id}/rename")
async def rename_session(session_id: str, req: RenameRequest):
    conversations.update_many(
        {"session_id": session_id},
        {"$set": {"session_name": req.new_name}}
    )
    return {"status": "renamed"}


# ---------------------------------------
# RUN SERVER
# ---------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
