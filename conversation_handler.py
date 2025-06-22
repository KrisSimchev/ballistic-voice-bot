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
from openai_functions.prompts import assistant_instructions

class ConversationHandler:
    def __init__(self, openai_thread_id, caller_number, tts_handler: TTSHandler):
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
        self.is_interrupted = False
        self.caller_number = caller_number

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
            self.tts_handler.play_thinking_sound()
            # Log the accumulated transcript
            logger.debug(f"generate_and_stream called with accumulated transcript: '{self.accumulated_transcript}'")
            
            # If we try to interrupt the AI too fast
            if time.time() - self.last_response_time < self.minimum_response_time:
                logger.debug(f"Skipping response generation due to minimum response time not met")
                return None

            # If we try to interrupt it
            if self.is_generating:
                logger.debug(f"AI is already generating, setting interrupted flag")
                self.is_interrupted = True
                # self.tts_handler.synthesize_and_play("Един момент.")
                while self.is_generating:
                    time.sleep(0.1)
            
            self.is_interrupted = False
            logger.debug(f"Starting to generate response")
            self.is_generating = True

            # Adding the user's question to the message
            message = self.openai_client.beta.threads.messages.create(
                thread_id=self.openai_thread_id,
                role="user",
                content=self.accumulated_transcript
            )

            # Resetting the transcripts
            self.accumulated_transcript = ""

            # Creating a stream for the response
            try:
                logger.debug(f"Starting OpenAI stream with thread_id: {self.openai_thread_id}")
                with self.openai_client.beta.threads.runs.stream(
                    thread_id=self.openai_thread_id,
                    assistant_id=self.openai_assistant_id,
                    instructions=assistant_instructions + f"The person is calling from this number: {int(self.caller_number)}",
                    event_handler=OpenAI_EventHandler(self),
                ) as stream:
                    stream.until_done()
            except Exception as e:
                logger.error(f"Error in OpenAI stream: {e}")
            finally:
                self.is_generating = False
                logger.debug(f"Finished generating response")
        else:
            logger.debug(f"generate_and_stream called but accumulated transcript is empty")

        return None

    def stop_speaking(self):
        self.tts_handler.clear_queue()
