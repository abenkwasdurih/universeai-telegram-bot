from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_stats():
    # Check Generations (Unified Queue & Logs)
    gen_res = supabase.table("generations").select("id", count="exact").eq("status", "processing").execute()
    gen_count = gen_res.count if gen_res.count is not None else 0
    
    # Check Pending in Generations
    pend_res = supabase.table("generations").select("id", count="exact").eq("status", "pending").execute()
    pend_count = pend_res.count if pend_res.count is not None else 0
    
    print(f"📊 Database Stats (Generations Table):")
    print(f"--------------------------------------")
    print(f"Generations (pending):    {pend_count}")
    print(f"Generations (processing): {gen_count}")
    
    if gen_count >= 12:
        print(f"\n⚠️ WARNING: Global concurrency limit reached (Limit: 12)!")
        print(f"This is why your bot might be stuck.")

if __name__ == "__main__":
    check_stats()
