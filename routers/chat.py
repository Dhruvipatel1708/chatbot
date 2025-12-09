from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import httpx

from config import (
    sessions_collection,
    SYSTEM_PROMPT,
    OLLAMA_API_URL,
    MODEL_NAME
)
from .helpers import clean_response, get_conversation_history

router = APIRouter(prefix="/chat", tags=["Chat"])


class MessageRequest(BaseModel):
    text: str
    session_id: str
    expertise_level: Optional[str] = "beginner"


@router.post("/")
async def chat(req: MessageRequest):

    # Validate session
    session = sessions_collection.find_one({"session_id": req.session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Load history
    history = get_conversation_history(req.session_id)

    # Build PROMPT (not messages)
    full_prompt = SYSTEM_PROMPT + "\n\n"

    for msg in history:
        full_prompt += f"{msg['role'].upper()}: {msg['content']}\n"

    full_prompt += f"USER: {req.text}\nASSISTANT: "
    print("\n\n===================== FULL PROMPT SENT TO OLLAMA =====================")
    print(full_prompt)
    print("====================================================================\n\n")

    # Save user message
    sessions_collection.update_one(
        {"session_id": req.session_id},
        {
            "$push": {
                "messages": {
                    "role": "user",
                    "content": req.text,
                    "timestamp": datetime.utcnow().isoformat()
                }
            },
            "$set": {"updated_at": datetime.utcnow()}
        }
    )

    # Call OLLAMA (non-streaming + prompt mode)
    async with httpx.AsyncClient(timeout=300) as client_http:
        res = await client_http.post(
            OLLAMA_API_URL,
            json={
                "model": MODEL_NAME,
                "prompt": full_prompt,
                "stream": False
            }
        )

    data = res.json()

    # Correct key → Ollama uses "response"
    bot_text = data.get("response", "")

    # Save assistant message
    sessions_collection.update_one(
        {"session_id": req.session_id},
        {
            "$push": {
                "messages": {
                    "role": "assistant",
                    "content": clean_response(bot_text),
                    "timestamp": datetime.utcnow().isoformat()
                }
            },
            "$set": {"updated_at": datetime.utcnow()}
        }
    )

    return {"response": clean_response(bot_text)}
