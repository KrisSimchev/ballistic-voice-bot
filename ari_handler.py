import json
import threading
import requests
import websocket
from scapy.all import sniff, IP, UDP
from config import ARI_BASE_URL, ARI_USERNAME, ARI_PASSWORD, APP_NAME
from utils import logger
from media_receiver import MediaReceiver
from openai_functions.OpenAIClient import openai_client
from time import time, sleep
from call_redirector import redirect_call


active_channels = {}
active_channels_lock = threading.Lock()
active_ports = []

def handle_stasis_start(channel_id):
    try:
        # Get the channel object from ARI
        response = requests.get(
            f"{ARI_BASE_URL}/channels/{channel_id}",
            auth=(ARI_USERNAME, ARI_PASSWORD)
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to get channel: {response.text}")
            return
        
        channel = response.json()

    
        response = requests.get(
            f"{ARI_BASE_URL}/channels/{channel_id}/rtp_statistics",
            auth=(ARI_USERNAME, ARI_PASSWORD)
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to get RTP statistics: {response.text}")
            return
            
        rtp_info = response.json()
        logger.info(f"RTP stats for channel {channel_id}: {json.dumps(rtp_info, indent=2)}")
        
        rtp_port = None  

        def detect_rtp_destination_port(packet):
            if packet.haslayer(IP) and packet.haslayer(UDP):
                src_ip = packet[IP].src
                dst_port = packet[UDP].dport
                
                if src_ip.startswith("46.19.210") and 10000 <= dst_port <= 20000 and dst_port not in active_ports:
                    logger.info(f"Detected RTP Destination Port from {src_ip}: {dst_port}")
                    active_ports.append(dst_port)
                    return dst_port
            return None
        
        logger.info("Starting packet sniffing to detect RTP port from 46.19.210.22...")
        packets = sniff(filter="udp portrange 10000-20000", count=25, timeout=65)
        
        for packet in packets:
            port = detect_rtp_destination_port(packet)
            if port:
                rtp_port = port
                break   
        
        if not rtp_port:
            logger.error(f"Could not determine RTP port for channel {channel_id}")
            return
        
        logger.info(f"Creating OPENAI thread")
        openai_thread = openai_client.get_client().beta.threads.create()
        openai_thread_id = openai_thread.id

        logger.info(f"Initiazlizing Media Receiver")
        receiver = MediaReceiver(channel_id, openai_thread_id)
        logger.info(f"setting media receiver port {rtp_port}")
        receiver.rtp_port = rtp_port
        
        if not receiver.start_deepgram():
            logger.error(f"Failed to start Deepgram for channel {channel_id}")
            return
            
        with active_channels_lock:
            active_channels[channel_id] = receiver
        

        logger.info(f"Creating thread")
        thread = threading.Thread(target=receiver.run)
        thread.daemon = True
        thread.start()
        
        logger.info(f"Successfully initialized channel {channel_id} with RTP port {rtp_port}")
        
    except Exception as e:
        logger.error(f"Error in handle_stasis_start: {e}")

def cleanup_channel(channel_id):
    try:
        with active_channels_lock:
            if channel_id in active_channels:
                receiver = active_channels[channel_id]
                receiver.stop_flag = True
                if receiver.rtp_port in active_ports:
                    active_ports.remove(receiver.rtp_port)
                    logger.info(f"Removed RTP port {receiver.rtp_port} from active_ports")
                receiver.cleanup()
                del active_channels[channel_id]
                
        response = requests.delete(
            f"{ARI_BASE_URL}/channels/{channel_id}",
            auth=(ARI_USERNAME, ARI_PASSWORD)
        )
        
        if response.status_code not in (200, 404):
            logger.error(f"Error deleting channel {channel_id}: {response.text}")
            
    except Exception as e:
        logger.error(f"Error in cleanup_channel: {e}")

def on_ari_message(ws, message):
    try:
        event = json.loads(message)
        event_type = event.get('type')
        
        if not event_type:
            return
            
        logger.info(f"Received ARI event: {event_type}")
        
        if event_type == "StasisStart":
            channel_id = event.get('channel', {}).get('id')
            if channel_id:
                handle_stasis_start(channel_id)
                
        elif event_type == "StasisEnd":
            channel_id = event.get('channel', {}).get('id')
            if channel_id:
                cleanup_channel(channel_id)
                
    except Exception as e:
        logger.error(f"Error processing ARI message: {e}")

def handle_ari_events():
    while True:
        try:
            ws_url = (
                f"ws://127.0.0.1:8088/ari/events?"
                f"api_key={ARI_USERNAME}:{ARI_PASSWORD}&"
                f"app={APP_NAME}&subscribeAll=true"
            )
            
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_ari_message,
                on_error=lambda ws, error: logger.error(f"ARI WebSocket error: {error}"),
                on_close=lambda ws, code, msg: logger.info(f"ARI WebSocket closed: {code} - {msg}")
            )
            
            ws.run_forever(ping_interval=30, ping_timeout=10)
            
        except Exception as e:
            logger.error(f"Error in ARI event handler: {e}")
            time.sleep(5)
