import os
from dotenv import load_dotenv
from openai import OpenAI

from config.training import MAX_TOKENS, MODEL, TEMPERATURE
from logger.setup import LoggerManager


load_dotenv()

class LLMManager:

    def __init__(self, logger_manager: LoggerManager) -> None:
        self._log_mgr = logger_manager

        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            self._log_mgr.log_message("API key is missing.", "ERROR")
            raise ValueError("API key is required for OpenAI client.")
        self.client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

        self._log_mgr.log_message(
            (f"Successfully initialised the {self.__class__.__name__} "
             "instance and the OpenAI client."),
            "DEBUG"
        )

    def call_api(self, prompt: str):
        try:
            completion = self.client.chat.completions.create(
                model=MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    },
                ],
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS
            )
            return completion
        except Exception as e:
            self._log_mgr.log_message(f"OpenAI API call failed: {e}", "ERROR")
            return