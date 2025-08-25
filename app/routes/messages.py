from fastapi import APIRouter
from bson import ObjectId
from app.database import db

router = APIRouter()

def oid(s: str) -> ObjectId:
    from fastapi import HTTPException
    try: return ObjectId((s or "").strip())
    except Exception: raise HTTPException(400, "Invalid user_id format")

@router.get("/{user_id}")
def my_messages(user_id: str):
    uoid = oid(user_id)
    out=[]
    for m in db["messages"].find({"user_id": uoid}).sort("created_at",-1):
        m["_id"]=str(m["_id"]); m["user_id"]=str(m["user_id"]); out.append(m)
    return {"count": len(out), "messages": out}
