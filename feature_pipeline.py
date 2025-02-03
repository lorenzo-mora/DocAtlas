from pathlib import Path
from logger.setup import LoggerManager
import config
import config.file_management
from indexing.file_manager import FileManager
from indexing.text_processor import TextProcessor
from indexing.vector_db import ChromaHandler


if __name__ == "__main__":

    logger_manager = LoggerManager(
        name=config.LOGGING["name"],
        folder_path=config.LOGGING["folder_path"],
        max_size=config.LOGGING["max_size"],
        console_level=config.LOGGING["console_level"],
        file_level=config.LOGGING["file_level"],
    )
    logger_manager.setup_logger()

    logger_manager.log_message(
        "The document indexing pipeline is executed.", "INFO")

    mgr = FileManager(logger_manager = logger_manager)  # PDF file manager
    chroma = ChromaHandler(logger_manager=logger_manager)  # ChromaDB Manager
    mgr.unavailable_uuids = chroma.get_current_ids()

    try:
        if Path(config.file_management.source_path).is_dir():
            logger_manager.log_message(
                "Specified path points to a folder. Its entire contents are downloaded.",
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
        processor = TextProcessor(file=doc, logger_manager=logger_manager)
        embds = processor.compute_embedding()

    for doc in mgr.docs:
        chroma.add_document(doc, stricted=True)
        logger_manager.log_message(f"Document {doc.metadata.id} completed.", "INFO")

    logger_manager.log_message("Pipeline successfully executed.", "INFO")
