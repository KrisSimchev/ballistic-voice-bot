import requests
import websocket
import threading
import json
import time

ARI_USERNAME = "voicebot"
ARI_PASSWORD = "supersecret"
ARI_BASE_URL = "http://127.0.0.1:8088/ari"
APP_NAME = "voicebot-ari"

def on_message(ws, message):
    event = json.loads(message)

    event_type = event.get('type')
    if not event_type:
        return

    print(f"Got ARI event: {event_type}")

    if event_type == "StasisStart":
        channel = event.get('channel', {})
        channel_id = channel.get('id')
        print(f"StasisStart on channel_id={channel_id}")

        url_answer = f"{ARI_BASE_URL}/channels/{channel_id}/answer"
        try:
            r = requests.post(url_answer, auth=(ARI_USERNAME, ARI_PASSWORD))
            r.raise_for_status()
            print("Channel answered successfully.")
        except Exception as e:
            print("Error answering channel:", e)

        try:
            url_create_bridge = f"{ARI_BASE_URL}/bridges"
            payload = {
                "type": "mixing",
                "name": "myBridge"
            }
            r = requests.post(url_create_bridge, json=payload, auth=(ARI_USERNAME, ARI_PASSWORD))
            r.raise_for_status()
            bridge_obj = r.json()
            bridge_id = bridge_obj["id"]
            print("Bridge created:", bridge_id)

            url_add = f"{ARI_BASE_URL}/bridges/{bridge_id}/addChannel?channel={channel_id}"
            r = requests.post(url_add, auth=(ARI_USERNAME, ARI_PASSWORD))
            r.raise_for_status()
            print("Channel added to bridge.")
        except Exception as e:
            print("Error creating/adding channel to bridge:", e)

    elif event_type == "StasisEnd":
        channel = event.get('channel', {})
        channel_id = channel.get('id')
        print(f"StasisEnd on channel_id={channel_id}")

def on_error(ws, error):
    print("WebSocket error:", error)

def on_close(ws, close_status_code, close_msg):
    print(f"WebSocket closed - status: {close_status_code}, msg: {close_msg}")

def on_open(ws):
    print("WebSocket connection opened")

def run_ari_websocket():
    ws_url = (
        f"ws://127.0.0.1:8088/ari/events"
        f"?api_key={ARI_USERNAME}:{ARI_PASSWORD}"
        f"&app={APP_NAME}"
        f"&subscribeAll=true"
    )

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    wst = threading.Thread(target=ws.run_forever)
    wst.daemon = True
    wst.start()

    while True:
        time.sleep(1)

if __name__ == "__main__":
    run_ari_websocket()
