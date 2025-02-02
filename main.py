import sys
import time
import threading
from utils import logger
from ari_handler import handle_ari_events, active_channels, cleanup_channel
from openai_functions.OpenAIClient import openai_client

def main():
    try:
        logger.info("Initializing openai client...")
        openai_client.create_assistant()

        logger.info("Starting ARI listener...")
        ari_thread = threading.Thread(target=handle_ari_events, daemon=True)
        ari_thread.start()
        
        logger.info(f"ARI listener running. Awaiting calls...")
        
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        # Cleanup all active channels
        for channel_id in list(active_channels.keys()):
            cleanup_channel(channel_id)
        sys.exit(0)

if __name__ == "__main__":
    main()
