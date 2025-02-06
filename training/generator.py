from typing import Any, Dict, List, Literal, Optional
import json_repair
from openai.types.chat.chat_completion import ChatCompletion

from ai_tools import LLMManager
import config
from config.training import PROMPT_FILE_PATH
from indexing.components import ContextualQA
from logger.setup import LoggerManager
from storage_utils.yaml_handler import YAMLManager


logger_manager = LoggerManager(
    module_name=__name__,
    project_name=config.LOGGING["project_name"],
    folder_path=config.LOGGING["folder_path"],
    max_size=config.LOGGING["max_size"],
    console_level=config.LOGGING["console_level"],
    file_level=config.LOGGING["file_level"],
)
logger_manager.setup_logger()


class ContextualizedQuestionsGenerator:

    ROLE_DEVELOPER = "developer"
    ROLE_USER = "user"

    def __init__(self) -> None:
        self.llm_manager = LLMManager()
        self.prompts = YAMLManager.read(PROMPT_FILE_PATH)

    def contextualize_prompt(self, context: str) -> str:
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
            logger_manager.log_message("Context is empty or None.", "ERROR")
            raise ValueError("Context cannot be empty or None.")

        instruction: Optional[str] = self.prompts.get('user_contextual_qa')

        if not instruction:
            logger_manager.log_message(
                "Unable to retrieve text for the prompt instructions.", "ERROR")
            raise KeyError("Prompt instruction `question_generation` not found in YAML file.")

        return f"\nContext: {context}\nQuestion: {instruction}"

    def generate(
            self,
            prompt_context: str,
            context_id: str
        ) -> Optional[ContextualQA]:
        """Generate questions based on the provided prompt context.

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
            logger_manager.log_message(
                "Prompt context is empty or invalid.", "ERROR")
            raise ValueError("Prompt context cannot be empty.")

        messages = self._build_messages(prompt_context)
        try:
            completion = self.llm_manager.call_api(messages)
            return self._process_response(completion, context_id)
        except Exception as e:
            logger_manager.log_message(
                f"Unable to complete current completion: {e}", "ERROR")
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
            logger_manager.log_message(
                "Developer prompt not found in YAML file. It is skipped.",
                "WARNING"
            )
        else:
            dev_msg = self._create_message(self.ROLE_DEVELOPER, dev_prompt)

        usr_prompt = self.contextualize_prompt(context=prompt_context)
        if usr_prompt is None:
            logger_manager.log_message("User prompt could not be contextualized.", "ERROR")
            raise ValueError("User prompt could not be contextualized.")
        usr_msg = self._create_message(self.ROLE_USER, usr_prompt)

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
            if role not in (self.ROLE_DEVELOPER, self.ROLE_USER):
                logger_manager.log_message(f"Invalid role: {role}", "ERROR")
                raise ValueError("Invalid role provided.")

            if not isinstance(text, str) or not text.strip():
                logger_manager.log_message("Invalid text content.", "ERROR")
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
            logger_manager.log_message(f"Error creating message: {e}", "ERROR")
            raise

    def _process_response(
            self,
            completion: ChatCompletion,
            prompt_context: str
        ) -> Optional[ContextualQA]:
        response = completion.choices[0].message.content
        if not response:
            logger_manager.log_message("No response could be generated.", "ERROR")
            return

        repaired_response = json_repair.repair_json(response, return_objects=True)
        if isinstance(repaired_response, tuple):
            repaired_response = repaired_response[0]

        context_response: Dict[str, Any] = {
            **repaired_response, # type: ignore
            'contextId': prompt_context
        }
        return ContextualQA.from_dict(context_response)