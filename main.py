# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  # 👈 add this

from app.database import db
from app.routes import auth, accounts, transactions, admin, loans, messages, users

app = FastAPI(title="Bank Management App")

# ----- CORS (React <-> FastAPI) -----
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        # "http://localhost:3000",
        # "http://127.0.0.1:3000",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Static files (for avatars, etc.) -----
# Serve /static/* from the local "static" directory (create it if missing)
# e.g. saved avatars at static/avatars/<file> will be accessible at /static/avatars/<file>
app.mount("/static", StaticFiles(directory="static"), name="static")

# ----- Routers -----
app.include_router(auth.router,         prefix="/auth",         tags=["Auth"])
app.include_router(users.router,        prefix="/users",        tags=["Users"])
app.include_router(accounts.router,     prefix="/accounts",     tags=["Accounts"])
app.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])
app.include_router(admin.router,        prefix="/admin",        tags=["Admin"])
app.include_router(loans.router,        prefix="/loans",        tags=["Loans"])
app.include_router(messages.router,     prefix="/messages",     tags=["Messages"])

# ----- Health / Root -----
@app.get("/")
def home():
    return {"message": "Welcome to Bank Management System 🚀"}

@app.get("/test-db")
def test_db():
    try:
        collections = db.list_collection_names()
        return {"status": "success", "collections": collections}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
