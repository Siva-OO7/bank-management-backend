from pymongo import MongoClient

MONGO_URI = "mongodb+srv://marylandoctaves:8GW6dBL8A9dJR3mc@cluster0.jag6xkl.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

client = MongoClient(MONGO_URI)

db = client["bank_management"]  # Database name (Atlas lo auto create avuthundi)
