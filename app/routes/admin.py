from fastapi import APIRouter, HTTPException
from bson import ObjectId
from app.database import db
from datetime import datetime

router = APIRouter()

def oid(s: str) -> ObjectId:
    try: return ObjectId((s or "").strip())
    except Exception: raise HTTPException(400, "Invalid id format")

@router.get("/customers")
def customers():
    out=[]
    for u in db["users"].find({}, {"password":0}):
        u["_id"]=str(u["_id"]); out.append(u)
    return {"count": len(out), "customers": out}

@router.get("/accounts")
def accounts():
    out=[]
    for a in db["accounts"].find({}):
        a["_id"]=str(a["_id"]); a["user_id"]=str(a["user_id"]); out.append(a)
    return {"count": len(out), "accounts": out}

@router.get("/loans")
def loans():
    out=[]
    for l in db["loans"].find({}).sort("created_at",-1):
        l["_id"]=str(l["_id"]); l["user_id"]=str(l["user_id"]); out.append(l)
    return {"count": len(out), "loans": out}

@router.post("/loans/{loan_id}/approve")
def approve_loan(loan_id: str):
    loid = oid(loan_id)
    loan = db["loans"].find_one({"_id": loid})
    if not loan: raise HTTPException(404, "Loan not found")
    db["loans"].update_one({"_id": loid}, {"$set": {"status": "approved", "approved_at": datetime.utcnow()}})
    db["messages"].insert_one({"user_id": loan["user_id"], "text": "Your loan is approved ✅", "created_at": datetime.utcnow()})
    return {"status":"success","loan_id": loan_id, "new_status":"approved"}

@router.post("/loans/{loan_id}/reject")
def reject_loan(loan_id: str):
    loid = oid(loan_id)
    loan = db["loans"].find_one({"_id": loid})
    if not loan: raise HTTPException(404, "Loan not found")
    db["loans"].update_one({"_id": loid}, {"$set": {"status": "rejected"}})
    db["messages"].insert_one({"user_id": loan["user_id"], "text": "Your loan is rejected ❌", "created_at": datetime.utcnow()})
    return {"status":"success","loan_id": loan_id, "new_status":"rejected"}
