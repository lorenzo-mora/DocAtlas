import os
from typing import Any, Dict, List
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat.chat_completion import ChatCompletion

import config
from config.training import MAX_TOKENS, MODEL, TEMPERATURE
from logger.setup import LoggerManager


load_dotenv()

logger_manager = LoggerManager(
    module_name=__name__,
    project_name=config.LOGGING["project_name"],
    folder_path=config.LOGGING["folder_path"],
    max_size=config.LOGGING["max_size"],
    console_level=config.LOGGING["console_level"],
    file_level=config.LOGGING["file_level"],
)
logger_manager.setup_logger()


class LLMManager:

    def __init__(
            self,
            model_id: str = MODEL
        ) -> None:
        self.model = model_id

        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger_manager.log_message("API key is missing.", "ERROR")
            raise ValueError("API key is required for OpenAI client.")

        self.client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

        logger_manager.log_message(
            (f"Successfully initialised the {self.__class__.__name__} "
             f"instance with {self.model} as model."),
            "DEBUG"
        )

    def call_api(self, messages: List[Dict[str, Any]]) -> ChatCompletion:
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages, # type: ignore
                temperature=TEMPERATURE,
                max_completion_tokens=MAX_TOKENS
            )
            return completion
        except Exception as e:
            raise Exception(f"OpenAI API call failed: {e}")