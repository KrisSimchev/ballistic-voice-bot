import logging
import ssl

# SSL configuration
ssl._create_default_https_context = ssl._create_unverified_context

def setup_logging():
    """Configure logging for the application."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("voicebot.log"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()
