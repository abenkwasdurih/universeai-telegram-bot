"""
Execute migration via Supabase's postgrest-py raw execution.
Uses the REST API to call a stored procedure or direct SQL.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

def run_sql_migration():
    """Execute ALTER TABLE via Supabase SQL API."""
    
    # Supabase provides a SQL execution endpoint for service_role key
    sql_endpoint = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    migrations = [
        "ALTER TABLE public.ai_models ADD COLUMN IF NOT EXISTS is_free_pro_5s BOOLEAN DEFAULT FALSE",
        "ALTER TABLE public.ai_models ADD COLUMN IF NOT EXISTS cost_pro_5s INTEGER DEFAULT 0",
        "ALTER TABLE public.ai_models ADD COLUMN IF NOT EXISTS cost_pro_10s INTEGER DEFAULT 0",
        "COMMENT ON COLUMN public.ai_models.is_free_pro_5s IS 'If true, 5-second videos are free for Pro users'",
        "COMMENT ON COLUMN public.ai_models.cost_pro_5s IS 'Credit cost for 5-second videos (Pro tier)'",
        "COMMENT ON COLUMN public.ai_models.cost_pro_10s IS 'Credit cost for 10-second videos (Pro tier)'"
    ]
    
    print("🔧 Running migrations via direct SQL...")
    print(f"📡 Target: {SUPABASE_URL}")
    print("-" * 50)
    
    # Try using Supabase's internal query endpoint (newer API)
    query_endpoint = f"{SUPABASE_URL}/pg/query"
    
    for idx, sql in enumerate(migrations, 1):
        print(f"\n[{idx}/3] Executing: {sql[:50]}...")
        
        try:
            # Method 1: Try pg/query endpoint
            resp = requests.post(
                query_endpoint,
                headers=headers,
                json={"query": sql}
            )
            
            if resp.status_code in [200, 201, 204]:
                print(f"  ✅ Success!")
            elif resp.status_code == 404:
                # Endpoint not available, show manual instructions
                print(f"  ⚠️ pg/query endpoint not available")
                raise Exception("Need manual execution")
            else:
                print(f"  ❌ Failed: {resp.status_code} - {resp.text[:100]}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")
            print("\n" + "=" * 60)
            print("📋 MANUAL MIGRATION REQUIRED")
            print("=" * 60)
            print("\nPlease run this SQL in Supabase SQL Editor:")
            print("\n```sql")
            for s in migrations:
                print(f"{s};")
            print("```")
            print(f"\n🌐 Open: https://supabase.com/dashboard/project/xbaewxnzlfxltvsjefvr/sql")
            return False
    
    return True

if __name__ == "__main__":
    success = run_sql_migration()
    if success:
        print("\n✅ All migrations completed successfully!")
