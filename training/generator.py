from typing import Optional
import json_repair

from ai_tools import LLMManager
from config.training import PROMPT_FILE_PATH
from logger.setup import LoggerManager
from training.utils import YAMLHandler


class QuestionsGenerator:

    def __init__(
            self,
            logger_manager: LoggerManager
        ) -> None:
        self._log_mgr = logger_manager

        self.llm_manager = LLMManager(logger_manager)
        self.prompts = YAMLHandler.read(PROMPT_FILE_PATH)

    def contextualize_question_prompt(self, context: str) -> str:
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
            self._log_mgr.log_message("Context is empty or None.", "ERROR")
            raise ValueError("Context cannot be empty or None.")

        instruction: Optional[str] = self.prompts.get('questions_generation')

        if not instruction:
            self._log_mgr.log_message(
                "Unable to retrieve text for the prompt instructions.", "ERROR")
            raise KeyError("Prompt instruction `question_generation` not found in YAML file.")

        return f"\nContext: {context}\nQuestion: {instruction}"

    def generate(self, prompt_context: str):
        """Generate questions based on the provided prompt context.

        Parameters
        ----------
        prompt_context : str
            The context to be used for generating questions.

        Returns
        -------
        dict
            A dictionary containing the processed response with the context.

        Raises
        ------
        ValueError
            If the prompt context is empty or invalid.
        """
        if not prompt_context:
            self._log_mgr.log_message(
                "Prompt context is empty or invalid.", "ERROR")
            raise ValueError("Prompt context cannot be empty.")

        prompt = self.contextualize_question_prompt(context=prompt_context)

        completion = self.llm_manager.call_api(prompt=prompt)

        return self._process_response(completion, prompt_context)

    def _process_response(self, completion, prompt_context: str):
        response = completion.choices[0].message.content
        if not response:
            self._log_mgr.log_message("No response could be generated.", "ERROR")
            return

        response = json_repair.repair_json(response, return_objects=True)
        response['context'] = prompt_context # type: ignore

        return response