import os
from dotenv import load_dotenv
from supabase import create_client
import boto3

# Load file .env
load_dotenv()

def test_env():
    print("--- 1. PENGECEKAN VARIABEL .ENV ---")
    vars_to_check = ["SUPABASE_URL", "SUPABASE_KEY", "R2_ACCESS_KEY_ID", "R2_BUCKET_NAME"]
    all_ok = True
    for var in vars_to_check:
        value = os.getenv(var)
        status = "✅ TERISI" if value else "❌ KOSONG (NONE)"
        if not value: all_ok = False
        # Menampilkan 5 karakter pertama saja untuk keamanan
        print(f"{var}: {status} ({str(value)[:5]}...)")
    return all_ok

def test_supabase():
    print("\n--- 2. PENGECEKAN KONEKSI SUPABASE ---")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    try:
        supabase = create_client(url, key)
        # Coba ambil 1 data dari tabel users
        res = supabase.table("users").select("count", count='exact').limit(1).execute()
        print(f"✅ KONEKSI BERHASIL! Berhasil terhubung ke tabel users.")
    except Exception as e:
        print(f"❌ KONEKSI GAGAL: {str(e)}")

def test_r2():
    print("\n--- 3. PENGECEKAN KONEKSI CLOUDFLARE R2 ---")
    try:
        s3 = boto3.client(
            's3',
            endpoint_url=f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        )
        s3.list_objects_v2(Bucket=os.getenv("R2_BUCKET_NAME"), MaxKeys=1)
        print("✅ KONEKSI R2 BERHASIL! Bucket dapat diakses.")
    except Exception as e:
        print(f"❌ KONEKSI R2 GAGAL: {str(e)}")

if __name__ == "__main__":
    if test_env():
        test_supabase()
        test_r2()
    else:
        print("\n⚠️ Perbaiki file .env Anda terlebih dahulu sebelum lanjut tes koneksi.")
