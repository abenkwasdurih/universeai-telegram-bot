import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def compare_tasks():
    print("--- MEMBANDINGKAN DATA WEB VS TELEGRAM ---")
    
    # Ambil task terakhir dari Web
    web_task = supabase.table("tasks").select("*").eq("source", "web").order("created_at", desc=True).limit(1).execute()
    
    # Ambil task terakhir dari Telegram
    tele_task = supabase.table("tasks").select("*").eq("source", "telegram").order("created_at", desc=True).limit(1).execute()

    if web_task.data:
        print("\n[DATA DARI WEB]")
        print(f"Model Name: {web_task.data[0].get('model_name')}")
        print(f"Prompt: {web_task.data[0].get('prompt')}")
        print(f"Extra Params: {web_task.data[0].get('aspect_ratio')}, {web_task.data[0].get('resolution')}")
    
    if tele_task.data:
        print("\n[DATA DARI TELEGRAM]")
        print(f"Model Name: {tele_task.data[0].get('model_name')}")
        print(f"Prompt: {tele_task.data[0].get('prompt')}")
        print(f"Extra Params: {tele_task.data[0].get('aspect_ratio')}, {tele_task.data[0].get('resolution')}")

if __name__ == "__main__":
    compare_tasks()
