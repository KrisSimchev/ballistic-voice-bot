from typing import Optional
from tts_handler import TTSHandler
import time
from typing_extensions import override
from openai import AssistantEventHandler
from openai import OpenAI
import re
from utils import logger
from openai_functions.OpenAIClient import openai_client
from openai_functions.OpenAI_EventHandler import OpenAI_EventHandler

class ConversationHandler:
    def __init__(self, openai_thread_id, tts_handler: TTSHandler):
        self.tts_handler = tts_handler
        logger.info(f"Initialized TTS")
        self.last_response_time = 0
        self.minimum_response_time = 0.1 # 100 miliseconds
        self.accumulated_transcript = ""
        self.openai_client = openai_client.get_client()
        self.openai_assistant_id = openai_client.get_assistant_id()
        self.openai_thread_id = openai_thread_id
        self.number_of_responses = 1
        self.current_response_number = 0
        self.is_generating = False
        self.is_waiting = False
        self.is_interrupted = False

    def handle_transcript(self, transcript: str, timestamp: float) -> None:
        """Handle incoming transcripts and determine when to trigger AI response"""
        if transcript.strip():
            self.accumulated_transcript += " " + transcript.strip()
        return None

    def generate_and_stream_test(self, timestamp: float) -> None:
        tts_transcripts = self.accumulated_transcript
        self.accumulated_transcript =""
        logger.info(f"Sending to tts: {tts_transcripts}")
        self.tts_handler.synthesize_and_play(tts_transcripts)
        return
    
    def generate_and_stream(self, timestamp: float) -> None:
        if self.accumulated_transcript.strip():
            # If we try to interrupt the AI too fast
            if time.time() - self.last_response_time < self.minimum_response_time:
                return None

            # If we try to interrupt it
            if self.is_generating:
                self.is_waiting = True
                self.tts_handler.synthesize_and_play("Един момент.")
                while self.is_generating:
                    time.sleep(0.1)
            
            self.is_waiting = False
        
            self.is_generating = True

            # Adding the user's question to the message
            message = self.openai_client.beta.threads.messages.create(
                thread_id=self.openai_thread.id,
                role="user",
                content=self.accumulated_transcript
            )       

            # Creating a stream for the response
            try:
                with self.openai_client.beta.threads.runs.stream(
                    thread_id=self.openai_thread.id,
                    assistant_id=self.openai_assistant.id,
                    instructions="",
                    event_handler=self.OpenAI_EventHandler(self),
                ) as stream:
                    stream.until_done()
            finally:
                self.is_generating = False

        # Resetting the transcripts
        self.accumulated_transcript = ""
        return None