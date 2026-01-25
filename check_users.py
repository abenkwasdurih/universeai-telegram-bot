import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def check_users():
    print("Checking users table...")
    try:
        # Fetch one user to see keys
        res = supabase.table("users").select("*").limit(1).execute()
        if res.data:
            print("Columns found:", res.data[0].keys())
        else:
            print("No users found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_users()
