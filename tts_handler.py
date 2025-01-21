import requests
from typing import Optional
import wave
import pyaudio
from elevenlabs import client, VoiceSettings
from config import ELEVEN_LABS_API_KEY, ELEVEN_LABS_VOICE_ID

class TTSHandler:
    def __init__(self):
        self.chunk_size = 1024
        self.sample_width = 2
        self.channels = 1
        self.sample_rate = 24000
        self.audio = pyaudio.PyAudio()
        self.client = client(api_key=ELEVEN_LABS_API_KEY)
        self.voice_settings = VoiceSettings(
            stability=0.5,
            similarity_boost=0.75
        )

    def stream_audio(self, audio_stream):
        """Stream audio directly to the phone using PyAudio"""
        stream = self.audio.open(
            format=self.audio.get_format_from_width(self.sample_width),
            channels=self.channels,
            rate=self.sample_rate,
            output=True
        )
        
        try:
            for chunk in audio_stream:
                stream.write(chunk)
        finally:
            stream.stop_stream()
            stream.close()

    def generate_and_stream(self, text: str) -> None:
        """Generate TTS audio and stream it directly"""
        try:
            audio_stream = self.client.generate(
                text=text,
                voice_id=ELEVEN_LABS_VOICE_ID,
                stream=True,
                voice_settings=self.voice_settings
            )
            self.stream_audio(audio_stream)
        except Exception as e:
            logger.error(f"Error generating/streaming TTS: {e}")
