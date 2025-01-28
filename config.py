from typing import Any, Dict


PDF_SOURCE_FOLDER: str = "./data"

LOGGING: Dict[str, Any] = dict(
    name = "docatlas",
    folder_path = "logs",
    max_size = 524288000,
    console_level = "DEBUG",
    file_level = "DEBUG"
)

file_to_extract: str = r"C:\Users\l.mora\Progetti\idee"