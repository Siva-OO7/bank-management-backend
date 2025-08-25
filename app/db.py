from motor.motor_asyncio import AsyncIOMotorClient
from decouple import config

MONGO_URL = config("MONGO_URL")
DB_NAME = config("DB_NAME")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]
