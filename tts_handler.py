import os
import wave
import logging
import requests
import numpy as np
import time
from typing import Optional, Dict
from collections import deque
from threading import Thread, Lock
from elevenlabs import ElevenLabs
from config import (
    ELEVEN_LABS_API_KEY,
    ELEVEN_LABS_VOICE_ID,
    ARI_BASE_URL,
    ARI_USERNAME,
    ARI_PASSWORD,
)
from scipy.signal import resample_poly

logger = logging.getLogger(__name__)

class TTSHandler:
    def __init__(self, channel_id: str):
        self.channel_id = channel_id
        self.client = ElevenLabs(api_key=ELEVEN_LABS_API_KEY)
        self.asterisk_sounds_dir = "/var/lib/asterisk/sounds/tts_audio"
        
        # Queue management
        self.audio_queue = deque()
        self.currently_playing = None
        self.queue_lock = Lock()
        self.playback_thread = Thread(target=self._process_queue, daemon=True)
        self.playback_thread.start()
        
        os.makedirs(self.asterisk_sounds_dir, exist_ok=True)

    def _get_playback_status(self, playback_id: str) -> Optional[str]:
        """Check the status of a playback through ARI."""
        try:
            status_url = f"{ARI_BASE_URL}/playbacks/{playback_id}"
            response = requests.get(status_url, auth=(ARI_USERNAME, ARI_PASSWORD))
            
            if response.ok:
                return response.json().get('state')
            return None
        except Exception as e:
            logger.error(f"Error checking playback status: {e}")
            return None

    def _play_through_ari(self, base_sound_name: str) -> Optional[str]:
        """Play audio through ARI and return the playback ID."""
        try:
            play_url = f"{ARI_BASE_URL}/channels/{self.channel_id}/play"
            params = {
                "media": f"sound:tts_audio/{base_sound_name}"
            }
            response = requests.post(play_url, params=params, auth=(ARI_USERNAME, ARI_PASSWORD))
            
            if not response.ok:
                logger.error(
                    f"Failed to queue playback (status {response.status_code}): {response.text}"
                )
                return None

            playback_id = response.json().get('id')
            logger.info(f"Successfully queued audio playback in ARI. Playback ID: {playback_id}")
            return playback_id

        except Exception as e:
            logger.error(f"Error in ARI playback request: {e}")
            return None

    def _process_queue(self):
        """Background thread to process the audio queue."""
        while True:
            if self.audio_queue and not self.currently_playing:
                with self.queue_lock:
                    base_name = self.audio_queue.popleft()
                    self.currently_playing = base_name
                
                playback_id = self._play_through_ari(base_name)
                if playback_id:
                    # Wait for playback to complete
                    while True:
                        status = self._get_playback_status(playback_id)
                        if status in [None, 'done', 'canceled', 'failed']:
                            break
                        time.sleep(0.1)  # Check every 100ms
                
                self.currently_playing = None
            
            time.sleep(0.1)  # Prevent CPU spinning

    def synthesize_and_play(self, ai_answer: str) -> None:
        base_name = f"tts_{abs(hash(ai_answer))}"
        asterisk_wav_path = os.path.join(self.asterisk_sounds_dir, base_name + ".wav")

        if not os.path.exists(asterisk_wav_path):
            try:
                audio_generator = self.client.text_to_speech.convert(
                    text=ai_answer,
                    voice_id=ELEVEN_LABS_VOICE_ID,
                    model_id="eleven_flash_v2_5",
                    output_format="pcm_24000",
                    language_code="bg"
                )
                audio_data = b''.join(chunk for chunk in audio_generator)

                # Convert to NumPy int16
                audio_array_24k = np.frombuffer(audio_data, dtype=np.int16)

                # Increase volume
                audio_array_24k = np.clip(audio_array_24k * 2.0, -32768, 32767).astype(np.int16)

                # Downsample to 8 kHz
                orig_rate = 24000
                desired_rate = 8000
                audio_array_8k = resample_poly(audio_array_24k, up=1, down=3)
                audio_array_8k = audio_array_8k.astype(np.int16)

                # Write WAV file
                with wave.open(asterisk_wav_path, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(desired_rate)
                    wf.writeframes(audio_array_8k.tobytes())

                logger.info(f"Wrote final WAV to: {asterisk_wav_path}")

            except Exception as e:
                logger.error(f"Error during TTS generation or saving WAV: {e}")
                return

        # Add to queue instead of playing immediately
        with self.queue_lock:
            self.audio_queue.append(base_name)
            logger.info(f"Added '{base_name}' to the playback queue. Queue size: {len(self.audio_queue)}")