import os
import wave
import logging
import requests
import numpy as np
from typing import Optional
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

        os.makedirs(self.asterisk_sounds_dir, exist_ok=True)

    def _play_through_ari(self, base_sound_name: str) -> None:
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
                return

            logger.info("Successfully queued audio playback in ARI.")
        except Exception as e:
            logger.error(f"Error in ARI playback request: {e}")

    def synthesize_and_play(self, ai_answer: str) -> None:
        base_name = f"tts_{abs(hash(ai_answer))}"
        asterisk_wav_path = os.path.join(self.asterisk_sounds_dir, base_name + ".wav")

        if not os.path.exists(asterisk_wav_path):
            try:
                audio_generator = self.client.text_to_speech.convert(
                    text=ai_answer,
                    voice_id=ELEVEN_LABS_VOICE_ID,
                    model_id="eleven_monolingual_v1",
                    output_format="pcm_24000",
                    language_code="BG"
                )
                audio_data = b''.join(chunk for chunk in audio_generator)

                # Convert to NumPy int16
                audio_array_24k = np.frombuffer(audio_data, dtype=np.int16)

                # Increase volume a bit (2.0 doubles amplitude) ---
                audio_array_24k = np.clip(audio_array_24k * 2.0, -32768, 32767).astype(np.int16)

                # Downsample to 8 kHz (telephony-friendly) using scipy.signal.resample_poly ---
                orig_rate = 24000
                desired_rate = 8000
                audio_array_8k = resample_poly(audio_array_24k, up=1, down=3)  # from 24k -> 8k
                audio_array_8k = audio_array_8k.astype(np.int16)

                # Write out the 8 kHz mono WAV
                with wave.open(asterisk_wav_path, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)  # 16-bit
                    wf.setframerate(desired_rate)
                    wf.writeframes(audio_array_8k.tobytes())

                logger.info(f"Wrote final WAV to: {asterisk_wav_path}")

            except Exception as e:
                logger.error(f"Error during TTS generation or saving WAV: {e}")
                return

        self._play_through_ari(base_name)
        logger.info("Playing TTS audio on the phone...")