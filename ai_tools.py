import os
from typing import Any, Dict, List
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat.chat_completion import ChatCompletion

import config.logging
from config.training import MAX_TOKENS, MODEL, TEMPERATURE
from logger.setup import LoggerManager


load_dotenv()

logger_manager = LoggerManager(
    module_name=__name__,
    project_name=config.logging.PROJECT_NAME,
    folder_path=config.logging.FOLDER_PATH,
    max_file_size=config.logging.MAX_SIZE,
    console_level=config.logging.CONSOLE_LEVEL,
    file_level=config.logging.FILE_LEVEL,
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

        self.client = OpenAI(api_key=api_key)

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