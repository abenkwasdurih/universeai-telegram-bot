import os
import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

class R2Helper:
    def __init__(self):
        self.account_id = os.getenv("R2_ACCOUNT_ID")
        self.access_key_id = os.getenv("R2_ACCESS_KEY_ID")
        self.secret_access_key = os.getenv("R2_SECRET_ACCESS_KEY")
        self.bucket_name = os.getenv("R2_BUCKET_NAME")
        self.public_url = os.getenv("R2_PUBLIC_URL").rstrip('/')

        self.s3_client = boto3.client(
            service_name='s3',
            endpoint_url=f'https://{self.account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name='auto',
            config=Config(signature_version='s3v4')
        )

    def upload_file(self, file_path, object_name, content_type='image/jpeg'):
        """Upload a file to R2 bucket"""
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, object_name, ExtraArgs={'ContentType': content_type})
            return f"{self.public_url}/{object_name}"
        except Exception as e:
            print(f"R2 Upload Error: {e}")
            return None

    def upload_bytes(self, file_bytes, object_name, content_type='image/jpeg'):
        """Upload bytes to R2 bucket"""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=object_name,
                Body=file_bytes,
                ContentType=content_type
            )
            return f"{self.public_url}/{object_name}"
        except Exception as e:
            print(f"R2 Upload Bytes Error: {e}")
            return None
    def upload_from_url(self, url, object_name, content_type='video/mp4'):
        """Download from URL and upload to R2"""
        try:
            import requests
            response = requests.get(url, timeout=60, stream=True)
            if response.status_code == 200:
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=object_name,
                    Body=response.content,
                    ContentType=content_type
                )
                return f"{self.public_url}/{object_name}"
            return None
        except Exception as e:
            print(f"R2 URL Upload Error: {e}")
            return None
