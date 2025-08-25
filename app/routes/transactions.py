from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from app.database import db
from typing import Optional

router = APIRouter()

# ----- Models -----
class DepositWithdraw(BaseModel):
    user_id: Optional[str] = None
    account_number: Optional[str] = None
    amount: float

class Transfer(BaseModel):
    from_user_id: Optional[str] = None
    to_user_id: Optional[str] = None
    from_account: Optional[str] = None
    to_account: Optional[str] = None
    amount: float

# ----- Helpers -----
def find_account(user_id: Optional[str], account_number: Optional[str]):
    if account_number:
        acc = db["accounts"].find_one({"account_number": account_number})
        if not acc:
            raise HTTPException(404, "Account not found (by account_number)")
        return acc

    if user_id:
        acc = db["accounts"].find_one({"user_id": user_id})
        if not acc:
            raise HTTPException(404, "Account not found (by user_id)")
        return acc

    raise HTTPException(400, "Provide either user_id or account_number")

def log_tx(user_id: str, tx_type: str, amount: float, balance_after: float, counterparty: Optional[str] = None):
    db["transactions"].insert_one({
        "user_id": user_id,   # always a string
        "type": tx_type,
        "amount": float(amount),
        "balance_after": float(balance_after),
        "counterparty_user_id": counterparty,
        "timestamp": datetime.utcnow(),
    })

# ----- Endpoints -----
@router.post("/deposit")
def deposit(req: DepositWithdraw):
    if req.amount <= 0:
        raise HTTPException(400, "Amount must be > 0")

    acc = find_account(req.user_id, req.account_number)
    db["accounts"].update_one({"_id": acc["_id"]}, {"$inc": {"balance": req.amount}})
    new_acc = db["accounts"].find_one({"_id": acc["_id"]})

    log_tx(new_acc["user_id"], "deposit", req.amount, new_acc["balance"])

    return {
        "status": "success",
        "new_balance": float(new_acc["balance"]),
        "account_number": new_acc["account_number"],
    }

@router.post("/withdraw")
def withdraw(req: DepositWithdraw):
    if req.amount <= 0:
        raise HTTPException(400, "Amount must be > 0")

    acc = find_account(req.user_id, req.account_number)
    if float(acc["balance"]) < req.amount:
        raise HTTPException(400, "Insufficient balance")

    db["accounts"].update_one({"_id": acc["_id"]}, {"$inc": {"balance": -req.amount}})
    new_acc = db["accounts"].find_one({"_id": acc["_id"]})

    log_tx(new_acc["user_id"], "withdraw", req.amount, new_acc["balance"])

    return {
        "status": "success",
        "new_balance": float(new_acc["balance"]),
        "account_number": new_acc["account_number"],
    }

@router.post("/transfer")
def transfer(req: Transfer):
    if req.amount <= 0:
        raise HTTPException(400, "Amount must be > 0")

    from_acc = find_account(req.from_user_id, req.from_account)
    to_acc   = find_account(req.to_user_id,   req.to_account)

    if float(from_acc["balance"]) < req.amount:
        raise HTTPException(400, "Insufficient balance")

    db["accounts"].update_one({"_id": from_acc["_id"]}, {"$inc": {"balance": -req.amount}})
    db["accounts"].update_one({"_id": to_acc["_id"]},   {"$inc": {"balance":  req.amount}})

    new_from = db["accounts"].find_one({"_id": from_acc["_id"]})
    new_to   = db["accounts"].find_one({"_id": to_acc["_id"]})

    log_tx(new_from["user_id"], "transfer_out", req.amount, new_from["balance"], counterparty=new_to["user_id"])
    log_tx(new_to["user_id"],   "transfer_in",  req.amount, new_to["balance"],   counterparty=new_from["user_id"])

    return {
        "status": "success",
        "from_account_new_balance": float(new_from["balance"]),
        "to_account_new_balance": float(new_to["balance"]),
        "from_account_number": new_from["account_number"],
        "to_account_number": new_to["account_number"],
    }

@router.get("/history/{user_id}")
def history(user_id: str):
    cur = db["transactions"].find({"user_id": user_id}).sort("timestamp", -1)
    out = []
    for t in cur:
        row = {
            "type": t["type"],
            "amount": float(t["amount"]),
            "balance_after": float(t["balance_after"]),
            "timestamp": t["timestamp"].isoformat() + "Z",
        }
        if t.get("counterparty_user_id"):
            if t["type"] == "transfer_out":
                row["to"] = t["counterparty_user_id"]
            elif t["type"] == "transfer_in":
                row["from"] = t["counterparty_user_id"]
        out.append(row)
    return {"status": "success", "transactions": out}
