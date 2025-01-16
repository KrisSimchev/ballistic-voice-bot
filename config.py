from dotenv import load_dotenv
import os

load_dotenv()

# ARI Configuration
ARI_USERNAME = os.getenv("ARI_USERNAME")
ARI_PASSWORD = os.getenv("ARI_PASSWORD")
ARI_BASE_URL = "http://127.0.0.1:8088/ari"
APP_NAME = "voicebot-ari"

# Deepgram Configuration
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
DG_SAMPLE_RATE = 8000
DG_LANGUAGE = "bg"
DG_MODEL = "nova-2"

# RTP Configuration
RTP_HOST = "0.0.0.0"
DEFAULT_RTP_PORT = 12000
