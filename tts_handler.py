import os
from elevenlabs import client, generate, Voice, VoiceSettings
import wave
import numpy as np
from typing import Optional
import logging
from config import ELEVEN_LABS_API_KEY, ELEVEN_LABS_VOICE_ID
logger = logging.getLogger(__name__)

class TTSHandler:
    def __init__(self, channel=None):
        self.channel = channel
        self.voice_settings = VoiceSettings(
            stability=0.5,
            similarity_boost=0.75,
            style=0.0,
            use_speaker_boost=True
        )
        self.output_dir = "tts_audio"
        # Create output directory if it doesn't exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
    def synthesize_and_play(self, text: str) -> None:
        """Generate TTS audio and play it through Asterisk"""
        try:
            # Generate unique filename
            filename = f"{self.output_dir}/tts_{hash(text)}.wav"
            
            # Generate audio if file doesn't exist
            if not os.path.exists(filename):
                # Generate audio from ElevenLabs
                audio = generate(
                    text=text,
                    voice=ELEVEN_LABS_VOICE_ID,
                    model="eleven_monolingual_v1",
                    api_key=ELEVEN_LABS_API_KEY,
                    voice_settings=self.voice_settings
                )
                
                # Convert to numpy array
                audio_array = np.frombuffer(audio, dtype=np.int16)
                
                # Increase volume (adjust multiplier as needed)
                audio_array = np.clip(audio_array * 2.0, -32768, 32767).astype(np.int16)
                
                # Save as WAV file
                with wave.open(filename, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit
                    wav_file.setframerate(24000)  # 24kHz
                    wav_file.writeframes(audio_array.tobytes())
            
            # Play through Asterisk ARI
            if self.channel:
                try:
                    self.channel.play(media='sound:' + filename)
                    logger.info(f"Playing TTS audio: {text[:50]}...")
                except Exception as e:
                    logger.error(f"Error playing audio through Asterisk: {e}")
            
        except Exception as e:
            logger.error(f"Error in TTS synthesis: {e}")
            
    def cleanup(self):
        """Clean up old TTS files"""
        try:
            for file in os.listdir(self.output_dir):
                if file.startswith("tts_") and file.endswith(".wav"):
                    file_path = os.path.join(self.output_dir, file)
                    # Delete files older than 1 hour
                    if os.path.getmtime(file_path) < time.time() - 3600:
                        os.remove(file_path)
        except Exception as e:
            logger.error(f"Error cleaning up TTS files: {e}")