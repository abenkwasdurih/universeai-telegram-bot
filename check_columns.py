import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

try:
    # Fetch one row to inspect keys
    res = supabase.table("ai_models").select("*").limit(1).execute()
    if res.data:
        keys = res.data[0].keys()
        print("Columns found:", keys)
        required = ['cost_pro_5s', 'cost_pro_10s', 'is_free_pro_5s']
        missing = [col for col in required if col not in keys]
        
        if missing:
            print(f"❌ MISSING COLUMNS: {missing}")
        else:
            print("✅ All columns present.")
            # Print value to see if data is populated
            print(f"Sample Data: {res.data[0]}")
    else:
        print("⚠️ No data in ai_models table.")
except Exception as e:
    print(f"Error: {e}")
