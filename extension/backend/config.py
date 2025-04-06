
import os
from dotenv import load_dotenv

load_dotenv() 

class Config:
  
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/mydb")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

  
    GOOGLE_CLIENT_SECRETS_FILE = os.getenv("GOOGLE_CLIENT_SECRETS_FILE", "google_client_secrets.json")
   
    GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid"
]
 
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        print("Warning: OPENAI_API_KEY environment variable not set.")

    TEMP_AUDIO_DIR = os.getenv("TEMP_AUDIO_DIR", "temp_audio")

    SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_key_for_dev")

if not os.path.exists(Config.TEMP_AUDIO_DIR):
    os.makedirs(Config.TEMP_AUDIO_DIR)