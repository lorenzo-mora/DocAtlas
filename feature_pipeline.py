import datetime
from pathlib import Path

import config
from config.chroma import AUTHOR
import config.file_management
from indexing.text_processor import TextProcessor
from logger.setup import LoggerManager
from storage_utils.db_hanler import DocumentCollectionHandler
from storage_utils.pdf_handler import PDFHandler


def run():
    logger_manager.log_message(
        "The document indexing pipeline is executed.", "INFO")

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

    logger_manager = LoggerManager(
        module_name=__name__,
        project_name=config.LOGGING["project_name"],
        folder_path=config.LOGGING["folder_path"],
        max_size=config.LOGGING["max_size"],
        console_level=config.LOGGING["console_level"],
        file_level=config.LOGGING["file_level"],
    )
    logger_manager.setup_logger()

    run()
