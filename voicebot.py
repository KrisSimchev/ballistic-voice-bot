import threading
import time
import requests
import json
import socket
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
import websocket
import logging
from config import *
import uuid

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("voicebot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


active_channels = {}  # Store channel info: {channel_id: RTPreceiver}
active_channels_lock = threading.Lock()  # Protect active_channels from race conditions

class RTPreceiver:
    def __init__(self, channel_id, bridge_id):
        self.channel_id = channel_id
        self.bridge_id = bridge_id
        self.stop_flag = False
        self.dg_connection = None
        self.packets_received = 0
        self.last_timestamp = None
        self.rtp_socket = None
        self.rtp_port = self._get_available_port()

    def _get_available_port(self, start_port=10000, end_port=20000):
        for port in range(start_port, end_port):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.bind(('0.0.0.0', port))
                    return port
            except OSError:
                continue
        raise RuntimeError("No available ports found")

    def start_deepgram(self):
        try:
            deepgram = DeepgramClient(api_key=DEEPGRAM_API_KEY)
            self.dg_connection = deepgram.listen.websocket.v("1")
            
            def on_transcript(transcript_data, **kwargs):
                if len(transcript_data.channel.alternatives) == 0:
                    return
                transcript = transcript_data.channel.alternatives[0].transcript
                if transcript.strip():
                    logger.info(f"[Channel {self.channel_id}] Transcript: {transcript}")
            
            def on_error(error, *args, **kwargs):
                logger.error(f"Deepgram error: {error}")
            
            self.dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
            self.dg_connection.on(LiveTranscriptionEvents.Error, on_error)
            
            options = LiveOptions(
                language=DG_LANGUAGE,
                model=DG_MODEL,
                sample_rate=8000,
                encoding="linear16",
                channels=1,
            )
            
            if not self.dg_connection.start(options):
                logger.error("Failed to start Deepgram connection")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Deepgram setup failed: {e}")
            return False
        
    def run(self):
        try:
            if not self.start_deepgram():
                logger.error("Deepgram setup failed")
                return
                
            logger.info(f"Started processing for channel {self.channel_id}")
            
            # Bind to RTP port
            if not self.rtp_socket:
                self.rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.rtp_socket.bind(('0.0.0.0', self.rtp_port))
                self.rtp_socket.settimeout(0.1)
                logger.info(f"Bound to RTP port {self.rtp_port}")

            while not self.stop_flag:
                logger.debug(f"Processing packets for channel {self.channel_id}")
                
                # Get the next RTP packet
                packet = self.get_next_rtp_packet()
                if packet:
                    # Process the packet
                    audio_data = self.process_rtp_packet(packet)
                    if audio_data:
                        # Send to Deepgram
                        self.dg_connection.send(audio_data)
                        self.packets_received += 1
                        logger.debug(f"Sent audio data to Deepgram (total packets: {self.packets_received})")
                    else:
                        logger.warning(f"Unprocessable RTP packet for channel {self.channel_id}")
                
                time.sleep(0.01)

        except Exception as e:
            logger.error(f"Error in receiver for channel {self.channel_id}: {e}")
        finally:
            self.cleanup()

    def process_rtp_packet(self, packet):
        try:
            if len(packet) < 12:
                logger.warning(f"Packet too small to be RTP: {len(packet)} bytes")
                return None
                
            # Log RTP header info for debugging
            version = (packet[0] >> 6) & 0x3
            padding = (packet[0] >> 5) & 0x1
            extension = (packet[0] >> 4) & 0x1
            csrc_count = packet[0] & 0x0F
            payload_type = packet[1] & 0x7F
            sequence = (packet[2] << 8) | packet[3]
            timestamp = (packet[4] << 24) | (packet[5] << 16) | (packet[6] << 8) | packet[7]
            
            logger.debug(f"RTP packet - Version: {version}, PT: {payload_type}, Seq: {sequence}, TS: {timestamp}")
            
            payload = packet[12:]  # Skip the RTP header
            if not payload:
                logger.warning("No payload in RTP packet")
                return None
                
            logger.debug(f"Extracted audio payload: {len(payload)} bytes")
            return payload
        except Exception as e:
            logger.error(f"Failed to process RTP packet: {e}")
            return None

    def get_next_rtp_packet(self):
        try:
            packet, addr = self.rtp_socket.recvfrom(2048)
            logger.info(f"Received RTP packet from {addr}, size: {len(packet)} bytes")
            return packet
        except socket.timeout:
            logger.debug("No RTP packet received (timeout)")
            return None
        except Exception as e:
            logger.error(f"Error receiving RTP packet: {e}")
            return None
    
    def cleanup(self):
        logger.info(f"Cleaning up channel {self.channel_id}")
        if self.dg_connection:
            try:
                self.dg_connection.finish()
            except Exception as e:
                logger.error(f"Error closing Deepgram connection: {e}")
        if self.rtp_socket:
            self.rtp_socket.close()
        self.dg_connection = None


# ARI Functions
def create_external_bridge(channel_id):
    try:
        bridge_id = f"external-bridge-{channel_id}"
        
        response = requests.post(
            f"{ARI_BASE_URL}/bridges",
            auth=(ARI_USERNAME, ARI_PASSWORD),
            json={"type": "mixing", "bridgeId": bridge_id}
        )
        if response.status_code != 200:
            logger.error(f"Failed to create bridge: {response.text}")
            return None
            
        response = requests.post(
            f"{ARI_BASE_URL}/bridges/{bridge_id}/addChannel",
            auth=(ARI_USERNAME, ARI_PASSWORD),
            params={"channel": channel_id}
        )
        if response.status_code != 204:
            logger.error(f"Failed to add channel to bridge: {response.text}")
            return None

        snoop_id = f"snoop-{channel_id}-{uuid.uuid4()}"
        response = requests.post(
            f"{ARI_BASE_URL}/channels/{channel_id}/snoop",
            auth=(ARI_USERNAME, ARI_PASSWORD),
            params={
                "app": APP_NAME,
                "spy": "both",
                "snoopId": snoop_id,
                "endpoint": "Local/s@default"
            }
        )
        if response.status_code not in [200, 204]:
            logger.error(f"Failed to create snoop: {response.text}")
            return None
            
        logger.info(f"Successfully created bridge {bridge_id}")
        return bridge_id
        
    except Exception as e:
        logger.error(f"Error setting up bridge: {e}")
        return None


def handle_new_channel(channel_id):
    bridge_id = create_external_bridge(channel_id)
    if not bridge_id:
        logger.error("Failed to create external media bridge")
        return
    
    receiver = RTPreceiver(channel_id, bridge_id)
    with active_channels_lock:
        active_channels[channel_id] = receiver
    
    thread = threading.Thread(target=receiver.run, daemon=True)
    thread.start()

def cleanup_channel(channel_id):
    if channel_id in active_channels:
        receiver = active_channels[channel_id]
        try:
            requests.delete(
                f"{ARI_BASE_URL}/bridges/{receiver.bridge_id}",
                auth=(ARI_USERNAME, ARI_PASSWORD)
            )
            logger.info(f"Deleted bridge {receiver.bridge_id}")
        except Exception as e:
            logger.error(f"Error deleting bridge: {e}")
        
        receiver.stop_flag = True
        del active_channels[channel_id]
        
        try:
            requests.delete(
                f"{ARI_BASE_URL}/channels/{channel_id}",
                auth=(ARI_USERNAME, ARI_PASSWORD)
            )
            logger.info(f"Deleted snoop channel {channel_id}")
        except Exception as e:
            logger.error(f"Error deleting snoop channel: {e}")


def on_ari_message(ws, message):
    event = json.loads(message)
    event_type = event.get('type')
    
    if not event_type:
        return
        
    logger.info(f"Got ARI event: {event_type}")
    
    if event_type == "StasisStart":
        channel = event.get('channel', {})
        channel_id = channel.get('id')
        
        if channel_id.startswith("snoop"):
            logger.info(f"Ignoring StasisStart event for snoop channel: {channel_id}")
            return

        logger.info(f"StasisStart on channel_id={channel_id}")
        
        try:
            requests.post(
                f"{ARI_BASE_URL}/channels/{channel_id}/answer",
                auth=(ARI_USERNAME, ARI_PASSWORD)
            )
            logger.info("Channel answered successfully")
        except Exception as e:
            logger.error(f"Error answering channel: {e}")
            return
            
        handle_new_channel(channel_id)
        
    elif event_type == "StasisEnd":
        channel = event.get('channel', {})
        channel_id = channel.get('id')
        logger.info(f"StasisEnd on channel_id={channel_id}")
        cleanup_channel(channel_id)


# Main Function
def handle_ari_events():
    ari_ws_url = (
        f"ws://127.0.0.1:8088/ari/events?"
        f"api_key={ARI_USERNAME}:{ARI_PASSWORD}&app={APP_NAME}&subscribeAll=true"
    )
    
    ws = websocket.WebSocketApp(
        ari_ws_url,
        on_message=on_ari_message,
        on_error=lambda ws, error: logger.error(f"ARI WebSocket error: {error}"),
        on_close=lambda ws, code, msg: logger.info(f"ARI WebSocket closed: {code} - {msg}")
    )
    ws.run_forever()

if __name__ == "__main__":
    logger.info("Starting ARI listener...")
    ari_thread = threading.Thread(target=handle_ari_events, daemon=True)
    ari_thread.start()
    
    logger.info(f"ARI listener running. Awaiting calls to app '{APP_NAME}'.")
    logger.info("Press Ctrl+C to exit.\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Exiting...")
