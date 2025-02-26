import datetime
from pathlib import Path

from config import schema
from config.chroma import AUTHOR
import config.logging
from config.file_management import PDF_SOURCE_FOLDER, source_path
from config.validation import ConfigurationError, validate_config
from storage.loading import Uploader
from text.extraction import TextExtractor
from text.processing import TextProcessor
from logger.setup import LoggerHandler
from storage.db_hanler import ParagraphsCollectionHandler


log_handler = LoggerHandler(
    folder_path=config.logging.FOLDER_PATH,
    max_file_size=config.logging.MAX_SIZE,
    backup_count=config.logging.MAX_NUM_FILE,
    console_level=config.logging.CONSOLE_LEVEL,
    file_level=config.logging.FILE_LEVEL,
    console_message_format=config.logging.CONSOLE_MESSAGE_FORMAT,
    console_date_format=config.logging.CONSOLE_DATE_FORMAT,
    file_date_format=config.logging.FILE_DATE_FORMAT,
    force_new_instance=True
)
log_handler.setup(namespace="feature_pipeline")
logger = log_handler.get_logger("feature_pipeline")

def run():
    logger.info(f"{chr(0x2699)} The document indexing pipeline is executed.")

    file_manager = Uploader(folder_path=PDF_SOURCE_FOLDER)  # PDF file uploader
    content_extractor = TextExtractor(folder_path=PDF_SOURCE_FOLDER)  # PDF file extractor
    processor = TextProcessor()  # Document textual content processor
    chroma = ParagraphsCollectionHandler(
        metadata={
            "description": (
                "Information of various files, such as file name, source path "
                "to sources, and the structured text chunks extracted from "
                "different pages and paragraphs."),
            "created": str(datetime.datetime.now()),
            "author": AUTHOR
        }
    )  # ChromaDB Manager for `documents` collction
    file_manager.unavailable_uuids = chroma.get_current_ids()

    try:
        if Path(source_path).is_dir():
            logger.info(
                "Specified path points to a folder. The entire content is downloaded."
            )
            file_manager.get_all_pdf_from_local_folder(source_path)
        else:
            logger.info("Specified path points to a single file.")
            file_manager.get_pdf_from_local(source_path, force=False)
    except Exception as e:
        logger.error(
            f"Error retrieving file `{source_path}`: {e}",
            exc_info=True
        )
        raise

    if not file_manager.docs_info:
        logger.warning(f"There is no file to be analysed")
        return

    for file in file_manager.docs_info:
        content_extractor.process_pdf_file(file)

    for doc in content_extractor.docs:
        processor.compute_embedding(file=doc)
        chroma.add_entry(doc, stricted=True)
        logger.info(f"Document {doc.metadata.id} [{doc.metadata.title}] completed.")

    logger.info("Pipeline successfully executed.")


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

    run()
