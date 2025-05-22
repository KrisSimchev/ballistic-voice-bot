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

# 11 labs Configuration
ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
ELEVEN_LABS_VOICE_ID = os.getenv("ELEVEN_LABS_VOICE_ID")

# OPENAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# SHOPIFY Configuration
SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY")
SHOPIFY_PASSWORD = os.getenv("SHOPIFY_PASSWORD")
SHOPIFY_API_VERSION = os.getenv("SHOPIFY_API_VERSION")
