import datetime
from pathlib import Path

from config import schema
from config.chroma import AUTHOR
import config.file_management
import config.logging
from config.validation import ConfigurationError, validate_config
from indexing.text_processor import TextProcessor
from logger.setup import LoggerManager
from storage_utils.db_hanler import DocumentCollectionHandler
from storage_utils.pdf_handler import PDFHandler


def run():
    logger_manager.log_message(
        f"{chr(0x2699)} The document indexing pipeline is executed.", "INFO")

    mgr = PDFHandler()  # PDF file manager
    processor = TextProcessor()  # Document textual content processor
    chroma = DocumentCollectionHandler(
        metadata={
            "description": (
                "Information of various files, such as file name, source path "
                "to sources, and the structured text chunks extracted from "
                "different pages and paragraphs."),
            "created": str(datetime.datetime.now()),
            "author": AUTHOR
        }
    )  # ChromaDB Manager
    mgr.unavailable_uuids = chroma.get_current_ids()

    try:
        if Path(config.file_management.source_path).is_dir():
            logger_manager.log_message(
                "Specified path points to a folder. The entire content is downloaded.",
                "INFO"
            )
            mgr.get_all_pdf_from_local_folder(config.file_management.source_path)
        else:
            logger_manager.log_message(
                "Specified path points to a single file.",
                "INFO"
            )
            mgr.get_pdf_from_local(config.file_management.source_path, force=False)
    except Exception as e:
        logger_manager.log_message(
            f"Error retrieving file `{config.file_management.source_path}`: {e}",
            level="ERROR",
            exc_info=True
        )
        raise

    if not mgr.docs_info:
        logger_manager.log_message(
            f"There is no file to be analysed",
            level="Warning"
        )
        exit(0)

    for file in mgr.docs_info:
        mgr.process_pdf_file(file)

    for doc in mgr.docs:
        processor.compute_embedding(file=doc)

    for doc in mgr.docs:
        chroma.add_entry(doc, stricted=True)
        logger_manager.log_message(
            f"Document {doc.metadata.id} [{doc.metadata.title}] completed.",
            "INFO"
        )

    logger_manager.log_message("Pipeline successfully executed.", "INFO")


if __name__ == "__main__":

    try:
        validate_config("config.chroma", schema.chroma_parameters)
        validate_config("config.embedding", schema.embedding_parameters)
        validate_config("config.file_management", schema.file_management_parameters)
        validate_config("config.logging", schema.logging_parameters)
        validate_config("config.processing_text", schema.processing_text_parameters)
        validate_config("config.redis", schema.redis_parameters)
        validate_config("config.training", schema.training_parameters)

    except ConfigurationError as e:
        raise Exception(f"{chr(0x274C)} Configuration Error: {e}")

    logger_manager = LoggerManager(
        module_name=__name__,
        project_name=config.logging.PROJECT_NAME,
        folder_path=config.logging.FOLDER_PATH,
        max_file_size=config.logging.MAX_SIZE,
        console_level=config.logging.CONSOLE_LEVEL,
        file_level=config.logging.FILE_LEVEL,
        console_message_format=config.logging.CONSOLE_MESSAGE_FORMAT
    )
    logger_manager.setup_logger()

    run()
