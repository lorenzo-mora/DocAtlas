from logger.setup import LoggerManager
import pandas as pd
import config
from file_manager import FileManager


if __name__ == "__main__":

    logger_manager = LoggerManager(
        name=config.LOGGING["name"],
        folder_path=config.LOGGING["folder_path"],
        max_size=config.LOGGING["max_size"],
        console_level=config.LOGGING["console_level"],
        file_level=config.LOGGING["file_level"],
    )
    logger_manager.setup_logger()


    mgr = FileManager(logger_manager = logger_manager)
    try:
        mgr.get_all_pdf_from_local_folder(config.file_to_extract)
    except Exception as e:
        logger_manager.log_message(
            f"Error retrieving file `{config.file_to_extract}`: {e}",
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


    pd.DataFrame(mgr.pages_map).to_csv(mgr.source_folder_path.joinpath("temp.csv"))

