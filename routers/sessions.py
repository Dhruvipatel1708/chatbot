# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel
# from datetime import datetime
# from config import sessions_collection

# router = APIRouter(prefix="/sessions", tags=["Sessions"])


# class NewSessionRequest(BaseModel):
#     session_id: str


# class RenameRequest(BaseModel):
#     new_name: str



# @router.post("/new")
# async def create_new_session(session_data: dict):
#     session_id = session_data.get("session_id")
#     session_name = session_data.get("session_name", "New Chat")
    
#     if not session_id:
#         raise HTTPException(status_code=400, detail="Session ID is required")
    
#     # Check if session already exists
#     if sessions_collection.find_one({"session_id": session_id}):
#         return {"status": "exists", "session_id": session_id}
    
#     # Create new session
#     session = {
#         "session_id": session_id,
#         "session_name": session_name,
#         "messages": [],
#         "created_at": datetime.utcnow(),
#         "updated_at": datetime.utcnow()
#     }
    
#     sessions_collection.insert_one(session)
#     return {"status": "created", "session_id": session_id}

# @router.get("/")
# async def get_sessions():
#     docs = sessions_collection.find().sort("updated_at", -1)
#     print("================")
#     result = []
#     for doc in docs:
#         preview = "New Chat"
#         for msg in doc.get("messages", []):
#             if msg["role"] == "user":
#                 preview = msg["content"].split("\n")[0].strip()
#                 break

#         result.append({
#             "session_id": doc["session_id"],
#             "session_name": doc.get("session_name", "New Chat"),
#             "preview": preview[:35] + "..." if len(preview) > 35 else preview,


# @router.put("/{session_id}/rename")
# async def rename_session(session_id: str, req: RenameRequest):
#     name = req.new_name.strip()
#     if not name:
#         raise HTTPException(status_code=400, detail="Name cannot be empty")

#     sessions_collection.update_one(
#         {"session_id": session_id},
#         {"$set": {"session_name": name, "updated_at": datetime.utcnow()}},
#     )

#     return {"status": "renamed"}
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
from config import sessions_collection
from routers.auth import get_current_user

router = APIRouter(prefix="/sessions", tags=["Sessions"])


class RenameRequest(BaseModel):
    new_name: str


@router.post("/new")
async def create_new_session(session_data: dict, user=Depends(get_current_user)):
    session_id = session_data.get("session_id")
    session_name = session_data.get("session_name", "New Chat")

    if not session_id:
        raise HTTPException(400, "Session ID is required")

    # check if exists for this user
    existing = sessions_collection.find_one({
        "session_id": session_id,
        "user_id": user["_id"]
    })

    if existing:
        return {"status": "exists", "session_id": session_id}

    session = {
        "session_id": session_id,
        "user_id": user["_id"],       # 👈 ADD THIS
        "session_name": session_name,
        "messages": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    sessions_collection.insert_one(session)
    return {"status": "created", "session_id": session_id}


@router.get("/")
async def get_sessions(user=Depends(get_current_user)):
    docs = sessions_collection.find({"user_id": user["_id"]}).sort("updated_at", -1)

    result = []
    for doc in docs:
        preview = "New Chat"
        for msg in doc.get("messages", []):
            if msg["role"] == "user":
                preview = msg["content"].split("\n")[0].strip()
                break

        result.append({
            "session_id": doc["session_id"],
            "session_name": doc.get("session_name", "New Chat"),
            "preview": preview[:35] + "..." if len(preview) > 35 else preview,
        })

    return {"sessions": result}


@router.get("/history/{session_id}")
async def get_history(session_id: str, user=Depends(get_current_user)):
    doc = sessions_collection.find_one({
        "session_id": session_id,
        "user_id": user["_id"]       # 👈 Only THIS user's sessions
    })

    if not doc:
        raise HTTPException(404, "Session not found")

    return {"messages": doc.get("messages", [])}


@router.delete("/{session_id}")
async def delete_session(session_id: str, user=Depends(get_current_user)):
    sessions_collection.delete_one({
        "session_id": session_id,
        "user_id": user["_id"]        # 👈 Don't delete others sessions!!
    })

    return {"status": "deleted"}


@router.put("/{session_id}/rename")
async def rename_session(session_id: str, req: RenameRequest, user=Depends(get_current_user)):
    name = req.new_name.strip()
    if not name:
        raise HTTPException(400, "Name cannot be empty")

    sessions_collection.update_one(
        {"session_id": session_id, "user_id": user["_id"]},
        {"$set": {"session_name": name, "updated_at": datetime.utcnow()}}
    )

    return {"status": "renamed"}
