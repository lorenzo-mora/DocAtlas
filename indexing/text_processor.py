import re
from typing import Optional

from sentence_transformers import SentenceTransformer

from config.embedding import (
    FIXED_EMBEDDING_LENGTH, MIN_CHUNK_LENGTH, MODEL_SENTENCE_TRANSFORMER
)
from indexing.components import Document
from logger.helper import timed_block
from logger.setup import LoggerManager


class TextProcessor:

    def __init__(
            self,
            logger_manager: LoggerManager,
            file: Document,
            fixed_length: Optional[int] = FIXED_EMBEDDING_LENGTH
        ) -> None:
        self._log_mgr = logger_manager
        self.file = file
        self.embedder_model = SentenceTransformer(
            MODEL_SENTENCE_TRANSFORMER,
            truncate_dim = fixed_length
        )

        self.embedding_size = self.embedder_model.get_sentence_embedding_dimension() or 384

        self._log_mgr.log_message(
            (f"Successfully initialised an instance {self.__class__.__name__} "
             f"for document {self.file.metadata.id}."),
            "DEBUG"
        )

    def process_text_data(self, chunk_length: int) -> None:
        """Processes the text data of each page in the document by
        removing paragraphs shorter than the specified chunk length and
        filtering out rows with five or more consecutive dots or dashes.

        Parameters
        ----------
        chunk_length : int
            The minimum length of paragraphs to retain. Must be a
            positive integer.

        Raises
        ------
        ValueError
            If `chunk_length` is not a positive integer.
        """
        if not isinstance(chunk_length, int) or chunk_length <= 0:
            raise ValueError(
                "The minimum length of the chunks must be a positive integer. "
                f"Instead, {chunk_length} has been provided."
            )

        self._log_mgr.log_message(
            f"Text extraction from the file `{self.file.metadata.title}` has begun.",
            "INFO"
        )

        # Set a regex pattern to identify rows with 5 or more
        # consecutive dots or dashes
        pattern_to_remove = r'(\.{5,}|\-{5,})'

        for page in self.file.pages:
            self._log_mgr.log_message(
                f"Page {page.number} processing started...",
                "DEBUG"
            )
            if bool(page.processed_text):
                # Text processing for this page has already been done
                self._log_mgr.log_message(
                    "Page already processed; it is skipped.", "WARNING")
                continue

            # Strip the text of the retrieved page, devided into
            # paragraphs, to remove leading and trailing spaces
            processed_text = list(map(
                str.strip, (chunk.raw_content for chunk in page.chunks)))

            # Filter paragraphs where the length of the text is greater
            # than chunk_length, removiing rows matching the pattern
            processed_text = [
                re.sub(pattern_to_remove, '', par)
                if len(par) > chunk_length else ''
                for par in processed_text
            ]

            for chunk, par in zip(page.chunks, processed_text):
                chunk.processed_content = par

            self._log_mgr.log_message("Page successfully processed.", "DEBUG")

        self._log_mgr.log_message(
            "Extraction from the current document successfully completed.",
            "INFO"
        )

    def compute_embedding(self, min_text_length: int = MIN_CHUNK_LENGTH) -> None:
        """Generates embeddings for processed text chunks using the
        `SentenceTransformer` model.

        Parameters
        ----------
        min_text_length : int
            The minimum length of text chunks to process.
        """
        self.process_text_data(min_text_length)

        self._log_mgr.log_message(
            f"Embedding generation for the document `{self.file.metadata.title}`.",
            "INFO"
        )

        # Generate embeddings for the proocessed text using the
        # SentenceTransformer model
        for page in self.file.pages:
            with timed_block(f"Embedding generation for page {page.number} took", self._log_mgr.get_logger()):

                step = int(len(page) * 0.22)  # Log about every 22% of completion
                for chunk_i, chunk in enumerate(page.chunks):

                    if step != 0 and (chunk_i + 1) % step == 0:
                        progress = (chunk_i + 1) / len(page) * 100
                        self._log_mgr.log_message(
                            f"{progress:.0f}% of the embeddings generation completed",
                            "DEBUG"
                        )

                    if chunk.processed_content:
                        try:
                            chunk.embedding = self.embedder_model.encode(
                                chunk.processed_content).tolist()
                        except Exception as e:
                            self._log_mgr.log_message(
                                f"Error in the generation of the embedding: {e}",
                                "WARNING"
                            )
                            chunk.embedding = [-0.0]*self.embedding_size

        self._log_mgr.log_message(
            "Embeddings for the current document were successfully elaborated.",
            "INFO"
        )