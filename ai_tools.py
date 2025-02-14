import os
from typing import Any, Dict, List
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat.chat_completion import ChatCompletion

from config.training import MAX_TOKENS, MODEL, TEMPERATURE
from logger.setup import LoggerHandler


load_dotenv()

logger = LoggerHandler().get_logger(__name__)

class LLMManager:
    """Manages interactions with the OpenAI API for language model operations.

    Attributes
    ----------
    model : str
        The identifier of the model used for API calls.
    client : OpenAI
        The OpenAI client instance for making API requests.

    Methods
    -------
    `call_api(messages: List[Dict[str, Any]])` -> ChatCompletion
        Calls the OpenAI API to generate a chat completion based on the
        provided messages.
    """

    _model_id: str

    def __init__(
            self,
            model_id: str = MODEL
        ) -> None:
        self.model = model_id

        self._api_key = os.environ.get('OPENAI_API_KEY')
        if not self._api_key:
            logger.error("API key is missing.")
            raise ValueError("API key is required for OpenAI client.")

        self.client = OpenAI(api_key=self._api_key)

        logger.debug(
            (f"Successfully initialised the {self.__class__.__name__} "
             f"instance with {self.model} as model."))

    @property
    def model(self) -> str:
        """The name of the current model."""
        return self._model_id

    @model.setter
    def model(self, value: str) -> None:
        if not isinstance(value, str):
            logger.error(
                f"Model id must be a string. Instead, a {type(value)} has been provided.")
            raise TypeError("invalid model id")
        self._model_id = value

    def call_api(self, messages: List[Dict[str, Any]]) -> ChatCompletion:
        """Calls the OpenAI API to generate a chat completion based on
        the provided messages.

        Parameters
        ----------
        messages : List[Dict[str, Any]]
            A list of message dictionaries to be sent to the API.

        Returns
        -------
        ChatCompletion
            The completion response from the OpenAI API.

        Raises
        ------
        Exception
            If the API call fails, an exception is raised with the error
            details.
        """
        logger.debug(
            f"Completion with content {messages} and temperature "
            f"{TEMPERATURE}, with maximum number of tokens equal to {MAX_TOKENS}."
        )
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages, # type: ignore
                temperature=TEMPERATURE,
                max_completion_tokens=MAX_TOKENS
            )
            return completion
        except Exception as e:
            logger.error(f"Exception occurred during API call: {e}")
            raise Exception(f"OpenAI API call failed: {e}")