from typing import Optional
from tts_handler import TTSHandler
import time
from typing_extensions import override
from openai import AssistantEventHandler
from openai import OpenAI
import re

class ConversationHandler:
    def __init__(self, tts_handler: TTSHandler):
        self.tts_handler = tts_handler
        self.last_response_time = 0
        self.minimum_response_time = 5
        self.is_speaking = False
        self.accumulated_transcript = ""
        #self.openai_client = client
        #self.openai_assistant = assistant
        #self.openai_thread = client.beta.threads.create()
        self.number_of_responses = 1
        self.current_response_number = 0
        self.is_generating = False

    class OpenAI_EventHandler(AssistantEventHandler):
        def __init__(self, conversation_handler):
            self.conversation_handler = conversation_handler
            self.current_sentence = ""
            
        @override
        def on_text_created(self, text) -> None:
            print(f"\nassistant > ", end="", flush=True)
            
        @override
        def on_text_delta(self, delta, snapshot):
            print(delta.value, end="", flush=True)
            
            # Add new text to our current sentence
            self.current_sentence += delta.value
            
            # Look for sentence endings
            if any(ending in self.current_sentence for ending in ['.', '!', '?']):
                # Find the last sentence ending
                last_end = max(
                    self.current_sentence.rfind('.'),
                    self.current_sentence.rfind('!'),
                    self.current_sentence.rfind('?')
                )
                
                if last_end != -1:
                    # Get the complete sentence
                    complete_sentence = self.current_sentence[:last_end + 1].strip()
                    # Keep the remaining text
                    self.current_sentence = self.current_sentence[last_end + 1:].strip()
                    
                    # Send to TTS if it's a valid sentence and we haven't exceeded responses
                    if complete_sentence and not self.conversation_handler.current_response_number > self.conversation_handler.number_of_responses:
                        self.conversation_handler.tts_handler.synthesize_and_play(complete_sentence)
            
        @override
        def on_tool_call_created(self, tool_call):
            print(f"\nassistant > {tool_call.type}\n", flush=True)

        @override
        def on_tool_call_delta(self, delta, snapshot):
            if delta.type == 'code_interpreter':
                if delta.code_interpreter.input:
                    print(delta.code_interpreter.input, end="", flush=True)
                if delta.code_interpreter.outputs:
                    print(f"\n\noutput >", flush=True)
                for output in delta.code_interpreter.outputs:
                    if output.type == "logs":
                        print(f"\n{output.logs}", flush=True)

    def handle_transcript(self, transcript: str, timestamp: float) -> None:
        """Handle incoming transcripts and determine when to trigger AI response"""
        if transcript.strip():
            self.accumulated_transcript += " " + transcript.strip()
        return None

    def generate_and_stream(self, timestamp: float) -> None:
        self.tts_handler.synthesize_and_play(self.accumulated_transcript)
        return 
        # If we try to interrupt the AI too fast
        if time.time() - self.last_response_time < self.minimum_response_time:
            return None
        
        self.last_response_time = timestamp
        self.current_response_number += 1

        # If we try to interrupt it
        if self.current_response_number > self.number_of_responses:
            self.tts_handler.synthesize_and_play("Please wait a second.")
            while self.is_generating:
                time.sleep(0.1)
        
        if self.accumulated_transcript.strip():
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
                self.number_of_responses += 1
            finally:
                self.is_generating = False

        # Resetting the transcripts
        self.accumulated_transcript = ""
        return None