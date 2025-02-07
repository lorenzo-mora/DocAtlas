from typing import Dict, Literal, Optional, Tuple


chroma_parameters = {
    "PERSIST_DIRRECTORY": str,
    "AUTHOR": str
}

embedding_parameters = {
    "FIXED_EMBEDDING_LENGTH": Optional[int],
    "MODEL_SENTENCE_TRANSFORMER": str
}

file_management_parameters = {
    "PDF_SOURCE_FOLDER": str,
    "OUTPUT_DESTINATION_FOLDER": str,
    "OVERWRITE_IF_EXISTS": bool,
    "UNIQUE_IF_EXISTS": bool,
    "TEXT_BOUNDARIES_PAGE": {
        "x": Tuple[float, float],
        "y": Tuple[float, float]
    },
    "source_path": str
}

logging_parameters = {
    "PROJECT_NAME": str,
    "FOLDER_PATH": str,
    "MAX_SIZE": int,
    "CONSOLE_LEVEL": Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    "FILE_LEVEL": Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    "CONSOLE_MESSAGE_FORMAT": Optional[str]
}

processing_text_parameters = {
    "STEPS": Dict[str, Dict[str, bool]],
    "MIN_CHUNK_LENGTH": Optional[int],
    "INSTALL_MISSING_NLTK": bool
}

redis_parameters = {
    "INDEX_NAME": str,
    "INDEX_TYPE": Literal["FLAT", "HNSW"],
    "DISTANCE_METRIC": str
}

training_parameters = {
    "PROMPT_FILE_PATH": str,
    "MODEL": str,
    "TEMPERATURE": float,
    "MAX_TOKENS": int
}