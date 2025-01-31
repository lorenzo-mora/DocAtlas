from typing import Any, Dict


LOGGING: Dict[str, Any] = dict(
    name = "docatlas",
    folder_path = "logs",
    max_size = 524288000,
    console_level = "DEBUG",
    file_level = "DEBUG"
)