from pathlib import Path
from typing import Any, Dict, Union
import yaml


class YAMLManager:

    @staticmethod
    def read(file_path: Union[Path, str]) -> Dict[str, Any]:
        """Reads a YAML file and returns its contents."""
        if not isinstance(file_path, Path):
            file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError("Unable to reach the specified path.")
        if file_path.is_dir():
            raise IsADirectoryError("Specified path points to a folder.")

        try:
            return yaml.safe_load(file_path.read_text(encoding='utf-8'))
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file: {e}")