from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime, timedelta
from passlib.context import CryptContext
import jwt
import os

from config import db

from fastapi import Depends, HTTPException
import jwt

# def get_current_user(token: str = Depends(lambda: None)):
#     try:
#         if not token:
#             raise HTTPException(401, "No token")

#         print("token",token)
#         payload = jwt.decode(token.split(" ")[1], SECRET_KEY, algorithms=[ALGO])
#         print("payload",payload)
#         user = users.find_one({"email": payload["email"]})
#         if not user:
#             raise HTTPException(401, "Invalid token")
#         return user
#     except Exception:
#         raise HTTPException(401, "Invalid or expired token")

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials        # <-- correct token extraction

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGO])
        user = users.find_one({"email": payload["email"]})
        if not user:
            raise HTTPException(401, "Invalid token")

        return user

    except Exception:
        raise HTTPException(401, "Invalid or expired token")


router = APIRouter(prefix="/auth", tags=["Auth"])

# ============================def get_current_user(token: str = Depends(lambda: None))
# Password hashing
# ============================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str):
    return pwd_context.verify(plain, hashed)

# ============================
# JWT Setup
# ============================
SECRET_KEY = os.getenv("JWT_SECRET", "testsecret123")
ALGO = "HS256"

def create_token(data: dict):
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(days=7)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGO)

# ============================
# Models
# ============================
class SignupModel(BaseModel):
    name: str
    email: str
    password: str

class LoginModel(BaseModel):
    email: str
    password: str


# ============================
# Collections
# ============================
users = db["users"]

# ============================
# Signup Route
# ============================
@router.post("/signup")
async def signup(data: SignupModel):

    existing = users.find_one({"email": data.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    hashed = data.password

    user = {
        "name": data.name,
        "email": data.email,
        "password": hashed,
        "created_at": datetime.utcnow(),
    }

    result = users.insert_one(user)
    user_id = str(result.inserted_id)

    token = create_token({"email": data.email})

    return {
        "access_token": token,
        "user": {
            "name": data.name,
            "email": data.email,
            "_id": user_id
        }
    }




# ============================
# Login Route
# ============================
@router.post("/login")
async def login(data: LoginModel):

    user = users.find_one({"email": data.email})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    if data.password != user["password"]:
    # if not verify_password(data.password, user["password"]):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    token = create_token({"email": user["email"]})

    return {
        "access_token": token,
        "user": {
            "name": user["name"],
            "email": user["email"]
        }
    }
