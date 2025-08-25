# backend/app/routes/users.py
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Optional
from bson import ObjectId

import os
from uuid import uuid4
from pathlib import Path
from fastapi import UploadFile, File, Request


from app.database import db
from app.security.passwords import verify_password, hash_password

# NOTE: main.py uses prefix="/users", so KEEP RELATIVE paths here.
router = APIRouter()

# ---------- helpers ----------
def find_user_by_id_any(user_id: str):
    """Find a user by _id that may be an ObjectId or a plain string."""
    # try ObjectId
    try:
        u = db.users.find_one({"_id": ObjectId(user_id)})
        if u:
            return u
    except Exception:
        pass
    # try plain string
    return db.users.find_one({"_id": user_id})

def find_user_by_account_number(acct_no: str):
    """Find (user, account) tuple by account_number. Accepts str/int formats."""
    acc = db.accounts.find_one({"account_number": str(acct_no)}) or db.accounts.find_one({"account_number": int(acct_no)}) if str(acct_no).isdigit() else None
    if not acc:
        return None, None
    uid = acc.get("user_id")
    # user_id in accounts may be stored as string; try both
    u = find_user_by_id_any(str(uid))
    return u, acc

def verify_password_with_legacy_support(plain: str, stored: str) -> bool:
    """Supports both bcrypt hashes and legacy plain text (if any existed)."""
    if not stored:
        return False
    if isinstance(stored, str) and stored.startswith("$2"):  # bcrypt marker
        try:
            return verify_password(plain, stored)
        except Exception:
            return False
    return plain == stored  # legacy fallback

# ---------- models ----------
class UserUpdate(BaseModel):
    username: Optional[str] = None
    dob: Optional[str] = None          # "YYYY-MM-DD"
    phone: Optional[str] = None
    address: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None
    time_zone: Optional[str] = None
    welcome: Optional[str] = None

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

class AccountDelete(BaseModel):
    current_password: str

# ---------- endpoints by USER ID (back-compat) ----------
@router.get("/{user_id}")
def get_user(user_id: str):
    u = find_user_by_id_any(user_id)
    if not u:
        raise HTTPException(404, detail="User not found")
    uid_str = str(u["_id"])
    acc = db.accounts.find_one({"user_id": uid_str}) or db.accounts.find_one({"user_id": u["_id"]})
    return {
        "status": "success",
        "user": {
            "id": uid_str,
            "username": u.get("username"),
            "email": u.get("email"),
            "dob": u.get("dob"),
            "phone": u.get("phone"),
            "address": u.get("address"),
            "country": u.get("country"),
            "language": u.get("language"),
            "time_zone": u.get("time_zone"),
            "welcome": u.get("welcome"),
            "created_at": u.get("created_at"),
            "last_login": u.get("last_login"),
        },
        "account": acc and {
            "account_number": acc.get("account_number"),
            "balance": acc.get("balance", 0),
        },
    }

@router.put("/{user_id}")
def update_user(user_id: str, body: UserUpdate):
    u = find_user_by_id_any(user_id)
    if not u:
        raise HTTPException(404, detail="User not found")
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if update:
        db.users.update_one({"_id": u["_id"]}, {"$set": update})
    return {"status": "success"}

@router.put("/{user_id}/password")
def change_password(user_id: str, payload: PasswordChange):
    u = find_user_by_id_any(user_id)
    if not u:
        raise HTTPException(404, detail="User not found")
    stored = u.get("password") or u.get("password_hash") or ""
    if not verify_password_with_legacy_support(payload.old_password, stored):
        raise HTTPException(status_code=400, detail="Old password incorrect")
    new_hash = hash_password(payload.new_password)
    field = "password_hash" if "password_hash" in u else "password"
    db.users.update_one({"_id": u["_id"]}, {"$set": {field: new_hash}})
    return {"status": "success"}

@router.delete("/{user_id}")
def delete_user(user_id: str, payload: AccountDelete = Body(...)):
    u = find_user_by_id_any(user_id)
    if not u:
        raise HTTPException(404, detail="User not found")
    stored = u.get("password") or u.get("password_hash") or ""
    if not verify_password_with_legacy_support(payload.current_password, stored):
        raise HTTPException(status_code=400, detail="Password incorrect")
    uid_str = str(u["_id"])
    db.transactions.delete_many({"user_id": uid_str})
    db.accounts.delete_many({"user_id": uid_str})
    db.users.delete_one({"_id": u["_id"]})
    return {"status": "success"}

# ---------- endpoints by ACCOUNT NUMBER (preferred) ----------
@router.get("/by-account/{account_number}")
def get_user_by_account(account_number: str):
    u, acc = find_user_by_account_number(account_number)
    if not u or not acc:
        raise HTTPException(404, detail="Account or user not found")
    uid_str = str(u["_id"])
    return {
        "status": "success",
        "user": {
            "id": uid_str,
            "username": u.get("username"),
            "email": u.get("email"),
            "dob": u.get("dob"),
            "phone": u.get("phone"),
            "address": u.get("address"),
            "country": u.get("country"),
            "language": u.get("language"),
            "time_zone": u.get("time_zone"),
            "welcome": u.get("welcome"),
            "created_at": u.get("created_at"),
            "last_login": u.get("last_login"),
        },
        "account": {
            "account_number": acc.get("account_number"),
            "balance": acc.get("balance", 0),
        },
    }

@router.put("/by-account/{account_number}")
def update_user_by_account(account_number: str, body: UserUpdate):
    u, acc = find_user_by_account_number(account_number)
    if not u or not acc:
        raise HTTPException(404, detail="Account or user not found")
    update = {k: v for k, v in body.model_dump().items() if v is not None}
    if update:
        db.users.update_one({"_id": u["_id"]}, {"$set": update})
    return {"status": "success"}

@router.put("/by-account/{account_number}/password")
def change_password_by_account(account_number: str, payload: PasswordChange):
    u, acc = find_user_by_account_number(account_number)
    if not u or not acc:
        raise HTTPException(404, detail="Account or user not found")
    stored = u.get("password") or u.get("password_hash") or ""
    if not verify_password_with_legacy_support(payload.old_password, stored):
        raise HTTPException(status_code=400, detail="Old password incorrect")
    new_hash = hash_password(payload.new_password)
    field = "password_hash" if "password_hash" in u else "password"
    db.users.update_one({"_id": u["_id"]}, {"$set": {field: new_hash}})
    return {"status": "success"}

@router.delete("/by-account/{account_number}")
def delete_by_account(account_number: str, payload: AccountDelete = Body(...)):
    u, acc = find_user_by_account_number(account_number)
    if not u or not acc:
        raise HTTPException(404, detail="Account or user not found")
    stored = u.get("password") or u.get("password_hash") or ""
    if not verify_password_with_legacy_support(payload.current_password, stored):
        raise HTTPException(status_code=400, detail="Password incorrect")
    # delete transactions that involve this account number either side
    an = str(acc.get("account_number"))
    db.transactions.delete_many({"from_account": an})
    db.transactions.delete_many({"to_account": an})
    # delete account doc
    db.accounts.delete_one({"account_number": an})
    # if you want to delete the user entirely (single-account system):
    db.users.delete_one({"_id": u["_id"]})
    return {"status": "success"}
