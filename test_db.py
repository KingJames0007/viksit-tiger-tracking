from src.db import get_all_tigers, get_db

try:
    db = get_db()
    print("Testing Supabase connection...")
    # Check if we can query tigers
    tigers = get_all_tigers()
    print("Connection successful! Enrolled tigers count:", len(tigers))
except Exception as e:
    print("Connection failed:", e)
