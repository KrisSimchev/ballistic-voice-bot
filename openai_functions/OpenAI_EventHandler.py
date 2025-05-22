from typing_extensions import override
from openai import AssistantEventHandler
from openai import OpenAI
from utils import logger
import json
from openai_functions.OpenAIClient import openai_client
from openai_functions.assistant_functions import track_order
import time

class OpenAI_EventHandler(AssistantEventHandler):
    def __init__(self, conversation_handler):
        super().__init__()
        self.conversation_handler = conversation_handler
        self.current_sentence = ""
        
    @override
    def on_text_created(self, text) -> None:
        full_response = text
        
    @override
    def on_text_delta(self, delta, snapshot):
        
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
            
            if last_end != -1 and not self.conversation_handler.is_interrupted:
                # Get the complete sentence
                complete_sentence = self.current_sentence[:last_end + 1].strip()
                # Keep the remaining text
                self.current_sentence = self.current_sentence[last_end + 1:].strip()
                
                # Send to TTS if it's a valid sentence and we haven't exceeded responses
                if complete_sentence:
                    self.conversation_handler.tts_handler.synthesize_and_play(complete_sentence)
        
    @override
    def on_tool_call_created(self, tool_call):
        logger.info(f"\nassistant > {tool_call.type}\n")

    @override
    def on_event(self, event):
        # Retrieve events that are denoted with 'requires_action'
        # since these will have our tool_calls
        if event.event == 'thread.run.requires_action':
            run_id = event.data.id  # Retrieve the run ID from the event data
            self.handle_requires_action(event.data, run_id)
    
    def handle_requires_action(self, data, run_id):
        tool_outputs = []
            
        for tool in data.required_action.submit_tool_outputs.tool_calls:
            if tool.function.name == "track_order":
                self.conversation_handler.tts_handler.synthesize_and_play("Проследявам поръчката Ви... Един момент..")
                arguments = json.loads(tool.function.arguments)
                order_identifier = arguments.get("order_identifier")
                logger.info(f"Tracking order: {order_identifier}")
                
                order_info = track_order(order_identifier)
                logger.info(f"Order info: {order_info}")
                tool_outputs.append({"tool_call_id": tool.id, "output": order_info})
                
            elif tool.function.name == "escalate_to_human":
                logger.info("Assistant requested to end the conversation.")
                escalate_to_human()
                self.end_thread(self.current_run.thread_id, run_id)
                return       
        # Submit all tool_outputs at the same time
        self.submit_tool_outputs(tool_outputs, run_id)
    
    def submit_tool_outputs(self, tool_outputs, run_id):
        # Use the submit_tool_outputs_stream helper
        with openai_client.get_client().beta.threads.runs.submit_tool_outputs_stream(
            thread_id=self.current_run.thread_id,
            run_id=self.current_run.id,
            tool_outputs=tool_outputs,
            event_handler=OpenAI_EventHandler(self.conversation_handler),
        ) as stream:
            stream.until_done()

    def end_thread(self, thread_id, run_id):
        """Forcefully stop the thread's run if necessary."""
        openai_client.get_client().beta.threads.runs.cancel(
            thread_id=thread_id,
            run_id=run_id
        )
        logger.info("OPENAI Thread has been manually ended.")
