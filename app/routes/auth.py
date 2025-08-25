from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from app.database import db
import random

router = APIRouter()

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    account_number: str
    new_password: str


@router.post("/register")
def register_user(req: RegisterRequest):
    users_collection = db["users"]
    accounts_collection = db["accounts"]

    # Prevent duplicate user
    existing = users_collection.find_one({
        "$or": [
            {"username": req.username},
            {"email": req.email}
        ]
    })
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    # Insert user
    result = users_collection.insert_one({
        "username": req.username,
        "email": req.email,
        "password": req.password
    })
    user_id = str(result.inserted_id)

    # Auto-create unique 8-digit savings account
    while True:
        acc_number = str(random.randint(10000000, 99999999))
        if not accounts_collection.find_one({"account_number": acc_number}):
            break

    accounts_collection.insert_one({
        "user_id": user_id,
        "account_number": acc_number,
        "account_type": "savings",
        "balance": 0
    })

    return {
        "status": "success",
        "message": "User + Account created successfully 🚀",
        "user": {
            "user_id": user_id,
            "username": req.username,
            "email": req.email,
            "account": {
                "account_number": acc_number,
                "account_type": "savings",
                "balance": 0
            }
        }
    }


@router.post("/login")
def login_user(req: LoginRequest):
    users_collection = db["users"]
    accounts_collection = db["accounts"]

    user = users_collection.find_one({
        "email": req.email,
        "password": req.password
    })
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    account = accounts_collection.find_one({"user_id": str(user["_id"])})

    return {
        "status": "success",
        "message": f"Welcome back, {user['username']} 🚀",
        "user": {
            "user_id": str(user["_id"]),
            "username": user["username"],
            "email": user["email"],
            "account": {
                "account_number": account["account_number"],
                "account_type": account["account_type"],
                "balance": account["balance"]
            } if account else None
        }
    }


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    users_collection = db["users"]
    accounts_collection = db["accounts"]

    # find user by email
    user = users_collection.find_one({"email": req.email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # check that the provided account belongs to them
    account = accounts_collection.find_one({
        "user_id": str(user["_id"]),
        "account_number": req.account_number
    })
    if not account:
        raise HTTPException(status_code=400, detail="Email and account number do not match")

    # update password
    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"password": req.new_password}}
    )

    return {"status": "success", "message": "Password reset successful 🚀"}
