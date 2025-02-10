from typing import Literal, Optional


# The path to the folder where all logging files will be saved.
FOLDER_PATH: str = "logs"

# The maximum size a logging file can take before a new one is created.
MAX_SIZE: int = 10485760  # 10 MB

# The maximum number of logging files that can be created for the
# current run.
MAX_NUM_FILE: int = 3

# The minimum level used for console messages.
CONSOLE_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

# The minimum level used for file messages.
FILE_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"

# The format in which messages are shown in the console.
CONSOLE_MESSAGE_FORMAT: Optional[str] = '%(asctime)s | %(name)s [ln %(lineno)d] - %(levelname)s : %(message)s'

# The console format of the timestamp associated with the message.
CONSOLE_DATE_FORMAT: Optional[str] = '%Y-%m-%d %H:%M:%S'

# The format in which the timestamp associated with the message is saved
# in the file.
FILE_DATE_FORMAT: Optional[str] = '%Y-%m-%d %H:%M:%S'
