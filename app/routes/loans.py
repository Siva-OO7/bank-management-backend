from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime
from app.database import db

router = APIRouter()

# ---------- models ----------
class EmiCalcRequest(BaseModel):
    amount: float
    annual_rate: float = Field(..., description="APR in %")
    months: int

class LoanApplyRequest(EmiCalcRequest):
    user_id: str

class PayEmiRequest(BaseModel):
    user_id: str
    loan_id: str
    amount: float

# ---------- helpers ----------
def oid(s: str) -> ObjectId:
    try:
        return ObjectId((s or "").strip())
    except Exception:
        raise HTTPException(400, "Invalid id format")

def calc_emi(p: float, apr: float, n: int) -> float:
    r = (apr/100)/12
    if r == 0:
        return round(p / n, 2)
    emi = p * r * (1 + r)**n / ((1 + r)**n - 1)
    return round(emi, 2)

def notify(user_oid: ObjectId, text: str):
    db["messages"].insert_one({
        "user_id": user_oid,
        "text": text,
        "created_at": datetime.utcnow()
    })

# ---------- endpoints ----------
@router.post("/emi-calc")
def emi_calc(req: EmiCalcRequest):
    return {"emi": calc_emi(req.amount, req.annual_rate, req.months)}

@router.post("/apply")
def apply(req: LoanApplyRequest):
    uoid = oid(req.user_id)
    if not db["accounts"].find_one({"user_id": uoid}):
        raise HTTPException(404, "Create a bank account first")

    emi = calc_emi(req.amount, req.annual_rate, req.months)
    doc = {
        "user_id": uoid,
        "amount": float(req.amount),
        "annual_rate": float(req.annual_rate),
        "months": int(req.months),
        "emi": float(emi),
        "status": "pending",
        "emis_paid": 0,
        "created_at": datetime.utcnow(),
    }
    res = db["loans"].insert_one(doc)
    notify(uoid, f"Loan request submitted. EMI ≈ ₹{emi:.2f}")
    return {"status":"success","loan_id": str(res.inserted_id), "emi": emi, "loan_status": "pending"}

@router.get("/my/{user_id}")
def my_loans(user_id: str):
    uoid = oid(user_id)
    rows = []
    for l in db["loans"].find({"user_id": uoid}).sort("created_at",-1):
        l["loan_id"] = str(l.pop("_id"))
        l["user_id"] = str(l["user_id"])
        rows.append(l)
    return {"status":"success","loans": rows}

@router.post("/pay-emi")
def pay_emi(req: PayEmiRequest):
    uoid, loid = oid(req.user_id), oid(req.loan_id)
    loan = db["loans"].find_one({"_id": loid, "user_id": uoid})
    if not loan: raise HTTPException(404, "Loan not found")
    if loan["status"] != "approved": raise HTTPException(400, "Loan not approved")
    # assume amount == EMI for now (simple)
    db["loans"].update_one({"_id": loid}, {"$inc": {"emis_paid": 1}})
    loan = db["loans"].find_one({"_id": loid})
    if loan["emis_paid"] >= loan["months"]:
        db["loans"].update_one({"_id": loid}, {"$set": {"status": "closed"}})
        notify(uoid, "All EMIs paid. No Dues ✅")
    else:
        notify(uoid, f"EMI received: ₹{req.amount:.2f}. EMIs paid: {loan['emis_paid']}/{loan['months']}")
    return {"status":"success","emis_paid": loan["emis_paid"], "months": loan["months"], "loan_status": loan.get("status","approved")}
