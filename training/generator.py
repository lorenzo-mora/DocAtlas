from typing import Any, Dict, List, Literal, Optional
import json_repair
from openai.types.chat.chat_completion import ChatCompletion

from ai_tools import LLMManager
from config.training import PROMPT_FILE_PATH
from text.components import ContextualQA
from logger.setup import LoggerHandler
from storage.yaml_handler import YAMLManager


logger = LoggerHandler().get_logger(__name__)

class ContextualQuestionResponseGenerator:
    """A class to generate, using a language model, questions and
    related answers, based on a given context and predefined prompts.

    Attributes
    ----------
    llm_manager : LLMManager
        An instance of LLMManager to handle language model interactions.
    prompts : Dict[str, Any]
        A dictionary containing predefined prompts loaded from a YAML
        file.

    Methods
    -------
    `generate(prompt_context: str, context_id: str)` -> Optional[ContextualQA]
        Generate questions based on the provided prompt context.
    """

    def __init__(self) -> None:
        self.llm_manager = LLMManager()
        self.prompts = YAMLManager.read(PROMPT_FILE_PATH)

    def generate(
            self,
            prompt_context: str,
            context_id: str,
        ) -> Optional[ContextualQA]:
        """Generate questions and their answers based on the provided
        prompt context.

        Parameters
        ----------
        prompt_context : str
            The context to be used for generating questions.
        context_id : str
            The unique identifier associated with the prompt context.

        Returns
        -------
        ContextualizedQuestions or None
            An object containing the processed response with the context,
            or None if no response could be generated.

        Raises
        ------
        ValueError
            If the prompt context is empty or invalid.
        """
        if not prompt_context:
            logger.error("Prompt context is empty or invalid.")
            raise ValueError("Prompt context cannot be empty.")

        messages = self._build_messages(prompt_context)
        try:
            completion = self.llm_manager.call_api(messages)
            return self._process_response(completion, context_id)
        except Exception as e:
            logger.error(f"Unable to complete current completion: {e}")
            raise

    def _build_messages(self, prompt_context: str) -> List[Dict[str, Any]]:
        """Build a list of message dictionaries for developer and user roles.

        Parameters
        ----------
        prompt_context : str
            The context to be used for generating the user prompt.

        Returns
        -------
        List[Dict[str, Any]]
            A list of message dictionaries, each containing a role and
            corresponding text content.

        Raises
        ------
        ValueError
            If the user prompt cannot be contextualized.
        """
        dev_prompt = self.prompts.get('developer_contextual_qa')
        dev_msg = None
        if dev_prompt is None:
            logger.warning(
                "Developer prompt not found in YAML file. It is skipped.")
        else:
            dev_msg = self._create_message("developer", dev_prompt)

        usr_prompt = self._contextualize_prompt(context=prompt_context)
        if usr_prompt is None:
            logger.error("User prompt could not be contextualized.")
            raise ValueError("User prompt could not be contextualized.")
        usr_msg = self._create_message("user", usr_prompt)

        return [msg for msg in [dev_msg, usr_msg] if msg is not None]

    def _create_message(
            self,
            role: Literal["developer", "user"],
            text: str
        ) -> Dict[str, Any]:
        """Create a message dictionary with a specified role and text content.

        Parameters
        ----------
        role : str, {"developer", "user"}
            The role of the message sender, must be either 'developer'
            or 'user'.
        text : str
            The text content of the message, must be a non-empty string.

        Returns
        -------
        Dict[str, Any]
            A dictionary containing the role and text content formatted
            for messaging.

        Raises
        ------
        ValueError
            If the role is invalid or the text content is empty or not a
            string.
        """
        try:
            if role not in ("developer", "user"):
                logger.error(f"Invalid role: {role}")
                raise ValueError("Invalid role provided.")

            if not isinstance(text, str) or not text.strip():
                logger.error("Invalid text content.")
                raise ValueError("Text content must be a non-empty string.")

            return {
                "role": role,
                "content": [
                    {
                        "type": "text",
                        "text": text
                    }
                ]
            }
        except ValueError as e:
            logger.error(f"Error creating message: {e}")
            raise

    def _contextualize_prompt(self, context: str) -> str:
        """Construct a question prompt by combining the provided context
        with predefined instructions for question generation.

        Parameters
        ----------
        context : str
            The context to be included in the question prompt.

        Returns
        -------
        str
            A formatted string containing the context and question
            instructions.

        Raises
        ------
        ValueError
            If the context is empty or None.
        KeyError
            If the question generation instructions are not found in the
            prompts.
        """
        if not context:
            logger.error("Context is empty or None.")
            raise ValueError("Context cannot be empty or None.")

        instruction: Optional[str] = self.prompts.get('user_contextual_qa')

        if not instruction:
            logger.error("Unable to retrieve text for the prompt instructions.")
            raise KeyError("Prompt instruction `question_generation` not found in YAML file.")

        return f"\nContext: {context}\nQuestion: {instruction}"

    def _process_response(
            self,
            completion: ChatCompletion,
            context_id: str
        ) -> Optional[ContextualQA]:
        """Process the response from a chat completion and convert it
        into a ContextualQA object.

        Parameters
        ----------
        completion : ChatCompletion
            The chat completion object containing the response to
            process.
        context_id : str
            The identifier of the context associated with the prompt.

        Returns
        -------
        Optional[ContextualQA]
            A ContextualQA object created from the processed response,
            or None if no valid response could be generated.
        """
        response = completion.choices[0].message.content
        if not response:
            logger.error("No response could be generated.")
            return

        repaired_response = json_repair.repair_json(response, return_objects=True)
        if isinstance(repaired_response, tuple):
            repaired_response = repaired_response[0]

        context_response: Dict[str, Any] = {
            **repaired_response, # type: ignore
            'context_id': context_id,
            'completion_id': completion.id
        }
        return ContextualQA.from_dict(context_response)