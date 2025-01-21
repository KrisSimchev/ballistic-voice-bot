from typing import Optional
from tts_handler import TTSHandler
import time

class ConversationHandler:
    def __init__(self, tts_handler: TTSHandler):
        self.tts_handler = tts_handler
        self.last_transcript_time = 0
        self.silence_threshold = 1.5  # seconds of silence to trigger AI response
        self.is_speaking = False
        self.accumulated_transcript = ""

    def get_ai_response(self, text: str) -> str:
        """Placeholder for AI response generation"""
        return "This is a test response. I heard what you said and I'm responding naturally."

    def handle_transcript(self, transcript: str, timestamp: float) -> Optional[str]:
        """Handle incoming transcripts and determine when to trigger AI response"""
        self.accumulated_transcript += " " + transcript
        self.last_transcript_time = timestamp
        
        # If we detect a natural pause (silence threshold exceeded)
        if time.time() - self.last_transcript_time > self.silence_threshold:
            if self.accumulated_transcript.strip():
                response = self.get_ai_response(self.accumulated_transcript)
                self.accumulated_transcript = ""  # Reset accumulated transcript
                return response
        return None
