from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId
from app.database import db
import random

router = APIRouter()

class AccountCreateRequest(BaseModel):
    user_id: str = Field(..., description="users._id (24-hex)")
    account_type: str = Field(..., pattern="^(savings|current)$")

def to_oid(s: str) -> ObjectId:
    try:
        return ObjectId((s or "").strip())
    except Exception:
        raise HTTPException(400, "Invalid user_id format")

def gen_acc_no() -> str:
    for _ in range(25):
        x = str(random.randint(10_000_000, 99_999_999))
        if not db["accounts"].find_one({"account_number": x}, {"_id": 1}):
            return x
    raise HTTPException(500, "Could not generate unique account number")

@router.post("/create")
def create_account(req: AccountCreateRequest):
    uoid = to_oid(req.user_id)
    if not db["users"].find_one({"_id": uoid}, {"_id": 1}):
        raise HTTPException(404, "User not found")

    # one account per user? if yes, guard it:
    if db["accounts"].find_one({"user_id": uoid}):
        raise HTTPException(400, "User already has an account")

    acc_no = gen_acc_no()
    doc = {
        "user_id": uoid,
        "account_number": acc_no,
        "account_type": req.account_type,
        "balance": 0.0,
    }
    db["accounts"].insert_one(doc)
    # respond JSON-friendly
    return {"status": "success", "message": "Account created", "account": {
        "user_id": str(uoid),
        "account_number": acc_no,
        "account_type": req.account_type,
        "balance": 0.0
    }}
