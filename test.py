from pathlib import Path
import unittest
import config.logging
from logger.setup import LoggerHandler

class Test_TestLoggerHandlerInstances(unittest.TestCase):
    def test_default(self):
        assert LoggerHandler() is LoggerHandler()

    def test_same_configuration(self):
        # First instance
        handler1 = LoggerHandler(
            folder_path=config.logging.FOLDER_PATH,
            max_file_size=config.logging.MAX_SIZE,
            backup_count=config.logging.MAX_NUM_FILE,
            console_level=config.logging.CONSOLE_LEVEL,
            file_level=config.logging.FILE_LEVEL,
            console_message_format=config.logging.CONSOLE_MESSAGE_FORMAT,
            console_date_format=config.logging.CONSOLE_DATE_FORMAT,
            file_date_format=config.logging.FILE_DATE_FORMAT
        )
        # Second instance with SAME config
        handler2 = LoggerHandler(
            folder_path=config.logging.FOLDER_PATH,
            max_file_size=config.logging.MAX_SIZE,
            backup_count=config.logging.MAX_NUM_FILE,
            console_level=config.logging.CONSOLE_LEVEL,
            file_level=config.logging.FILE_LEVEL,
            console_message_format=config.logging.CONSOLE_MESSAGE_FORMAT,
            console_date_format=config.logging.CONSOLE_DATE_FORMAT,
            file_date_format=config.logging.FILE_DATE_FORMAT
        )
        assert handler1 is handler2

    def test_singleton_pattern_creates_single_instance(self):
        # First instance
        handler1 = LoggerHandler(
            folder_path="./logs",
            max_file_size=1024,
            backup_count=2,
            force_new_instance=True
        )
    
        # Second instance with DIFFERENT config
        handler2 = LoggerHandler(
            folder_path="./other_logs",
            max_file_size=2048,
            backup_count=3
        )
    
        # Assert both references point to same instance
        assert handler1 is handler2
    
        # Assert config matches first instance
        assert handler1.log_dir == Path("./logs")
        assert handler1.max_size == 1024
        assert handler1.backup_count == 2

    def test_different_folder_path(self):
        # First instance
        handler1 = LoggerHandler(
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

        # Second instance with DIFFERENT `folder_path`
        handler2 = LoggerHandler(
            folder_path=r".\data",
            max_file_size=config.logging.MAX_SIZE,
            backup_count=config.logging.MAX_NUM_FILE,
            console_level=config.logging.CONSOLE_LEVEL,
            file_level=config.logging.FILE_LEVEL,
            console_message_format=config.logging.CONSOLE_MESSAGE_FORMAT,
            console_date_format=config.logging.CONSOLE_DATE_FORMAT,
            file_date_format=config.logging.FILE_DATE_FORMAT
        )
        assert handler1 is handler2

        # Assert config matches first instance
        assert handler2.log_dir == Path(config.logging.FOLDER_PATH)
        assert handler2.max_size == config.logging.MAX_SIZE
        assert handler2.backup_count == config.logging.MAX_NUM_FILE

    def test_different_namespace(self):
        # First instance
        handler1 = LoggerHandler(
            folder_path=config.logging.FOLDER_PATH,
            max_file_size=config.logging.MAX_SIZE,
            backup_count=config.logging.MAX_NUM_FILE,
            console_level=config.logging.CONSOLE_LEVEL,
            file_level=config.logging.FILE_LEVEL,
            console_message_format=config.logging.CONSOLE_MESSAGE_FORMAT,
            console_date_format=config.logging.CONSOLE_DATE_FORMAT,
            file_date_format=config.logging.FILE_DATE_FORMAT
        ).setup("first_step")

        # Second instance with SAME config but different `namespace`
        handler2 = LoggerHandler(
            folder_path=r".\data",
            max_file_size=config.logging.MAX_SIZE,
            backup_count=config.logging.MAX_NUM_FILE,
            console_level=config.logging.CONSOLE_LEVEL,
            file_level=config.logging.FILE_LEVEL,
            console_message_format=config.logging.CONSOLE_MESSAGE_FORMAT,
            console_date_format=config.logging.CONSOLE_DATE_FORMAT,
            file_date_format=config.logging.FILE_DATE_FORMAT
        ).setup("second_step")
        assert handler1 is handler2

    def test_force_new_instance(self):
        # First instance
        handler1 = LoggerHandler(
            folder_path=config.logging.FOLDER_PATH,
            max_file_size=config.logging.MAX_SIZE,
            backup_count=config.logging.MAX_NUM_FILE,
            console_level=config.logging.CONSOLE_LEVEL,
            file_level=config.logging.FILE_LEVEL,
            console_message_format=config.logging.CONSOLE_MESSAGE_FORMAT,
            console_date_format=config.logging.CONSOLE_DATE_FORMAT,
            file_date_format=config.logging.FILE_DATE_FORMAT
        )

        # Second instance with DIFFERENT `folder_path`
        handler2 = LoggerHandler(
            folder_path=r".\data",
            max_file_size=1024,
            backup_count=1,
            console_level="DEBUG",
            file_level="ERROR",
            console_message_format='%(asctime)s | %(levelname)s - %(lineno)d : %(message)s',
            console_date_format="%Y-%m-%d",
            file_date_format="%Y-%m-%d",
            force_new_instance=True
        )
        assert handler2 is not handler1

        # Assert config matches first instance
        assert handler2.log_dir != Path(config.logging.FOLDER_PATH)
        assert handler2.max_size != config.logging.MAX_SIZE
        assert handler2.backup_count != config.logging.MAX_NUM_FILE

if __name__ == '__main__':
    unittest.main()