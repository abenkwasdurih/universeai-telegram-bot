import os
import json
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase = create_client(url, key)

try:
    res = supabase.table("ai_models").select("*").eq("is_active_telegram", True).execute()
    if res.data:
        print(f"Found {len(res.data)} models active for Telegram.")
        for m in res.data:
            print("-" * 40)
            print(f"Model ID: {m.get('model_id')}")
            print(f"Name: {m.get('display_name')}")
            print(f"Legacy credit_cost: {m.get('credit_cost')}")
            print(f"cost_pro: {m.get('cost_pro')}")
            print(f"cost_pro_5s: {m.get('cost_pro_5s')}")
            print(f"cost_pro_10s: {m.get('cost_pro_10s')}")
            print(f"is_free_pro_5s: {m.get('is_free_pro_5s')}")
    else:
        print("No active models found.")

except Exception as e:
    print(f"Error: {e}")
