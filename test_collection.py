from pymongo import MongoClient
from pprint import pprint

# Connect to your MongoDB (same as in your config.py)
client = MongoClient('mongodb://localhost:27017/')
db = client['chatbot']  # replace with your database name

def check_sessions():
    print("=== All Sessions ===")
    sessions = list(db.sessions.find({}, {"session_id": 1, "user_id": 1, "session_name": 1, "_id": 0}))
    pprint(sessions)
    
    print("\n=== Specific Session ===")
    specific_session = db.sessions.find_one({"session_id": "sess-1765273137851"})
    pprint(specific_session)
    
    print("\n=== Users ===")
    users = list(db.users.find({}, {"email": 1, "_id": 1, "name": 1}))
    pprint(users)

if __name__ == "__main__":
    check_sessions()