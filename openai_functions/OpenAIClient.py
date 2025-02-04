# openai_client.py
import openai
from threading import Lock
from config import OPENAI_API_KEY
import os
import json
from openai_functions.prompts import assistant_instructions
from utils import logger

class OpenAIClient:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        """Ensures only one instance of OpenAIClient is created (Singleton Pattern)."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(OpenAIClient, cls).__new__(cls)
                cls._instance.client = None
                cls._instance.assistant_id = None
                cls._instance.vector_store_id = None
            return cls._instance

    def create_assistant(self):
        """Initializes the OpenAI client and stores the assistant ID."""
        if self.client is None:
            self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            assistant_file_path = 'assistant.json'

            if os.path.exists(assistant_file_path):
                with open(assistant_file_path, 'r') as file:
                    assistant_data = json.load(file)
                    self.assistant_id = assistant_data['assistant_id']
                    self.vector_store_id = assistant_data['vector_store_id']
                    logger.info("Loaded existing assistant ID.")
            else:
                vector_store = self.client.beta.vector_stores.create(name="Knowledge about Ballistic Sport")
                vector_store_id=vector_store.id

                file_paths = [
                    "Knowledge.docx", 
                ]

                for path in file_paths:
                    if not os.path.exists(path):
                        logger.info(f"File not found: {path}")
                
                file_streams = [open(path, "rb") for path in file_paths]

                file_batch = self.client.beta.vector_stores.file_batches.upload_and_poll(
                    vector_store_id=vector_store.id, 
                    files=file_streams
                )

                logger.info("Vector store created!")
                logger.info(file_batch.status)
                logger.info(file_batch.file_counts)

                assistant = self.client.beta.assistants.create(
                    instructions=assistant_instructions,
                    model="gpt-4o",
                    tools=[{
                        "type": "file_search",
                        "type": "function",
                        "function": {
                            "name": "track_order",
                            "description": "Tracking orders by customer's either: 1. Phone number 2. Email 3. Order number",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "order_identifier": {
                                        "type": "string",
                                        "description": "The customer's either email, phone number or order number"
                                    }
                                },
                                "required": [
                                    "order_identifier"
                                ],
                                "additionalProperties": False
                            },
                                "strict": True
                        },
                    }
                    ],
                    tool_resources={"file_search": {"vector_store_ids": [vector_store_id]}},
                )

                with open(assistant_file_path, 'w') as file:
                    IDs = {
                        'assistant_id': assistant.id,
                        'vector_store_id': vector_store_id
                    }
                    json.dump(IDs, file)

                self.assistant_id = assistant.id
                self.vector_store_id = vector_store_id

                logger.info(" OpenAI assistant created.")
        else:
            logger.info("OpenAI Client is already initialized.")

    def get_client(self):
        """Returns the OpenAI client instance."""
        return self.client

    def get_assistant_id(self):
        """Returns the assistant ID."""
        return self.assistant_id

# Global instance
openai_client = OpenAIClient()
