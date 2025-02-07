from typing import Literal, Optional


PROJECT_NAME: str = "docatlas"

FOLDER_PATH: str = "logs"

MAX_SIZE: int = 10485760  # 10 MB

CONSOLE_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

FILE_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"

CONSOLE_MESSAGE_FORMAT: Optional[str] = '%(asctime)s | %(levelname)s :: %(message)s'