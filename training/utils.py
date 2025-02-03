
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import yaml

from config.file_management import OUTPUT_DESTINATION_FOLDER
from logger.setup import LoggerManager


class YAMLManager:

    def __init__(
            self,
            logger_manager: LoggerManager,
            folder_path: Union[str, Path] = OUTPUT_DESTINATION_FOLDER
        ) -> None:
        self._log_mgr = logger_manager
        self.destination_folder_path = self._validate_destination_folder(folder_path)

    def _validate_destination_folder(self, path: Union[str, Path]) -> Path:
        path = Path(path)

        if path.exists() and not path.is_dir():
            raise ValueError("Specified path does not point to a folder")

        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

        return path

    def save(
            self,
            data: List[Tuple],
            file_name: str,
            destination_file_path: Union[Path, str] = "output.yaml"
        ) -> None:
        if not isinstance(destination_file_path, Path):
            destination_file_path = Path(destination_file_path)

        yaml_data = {
            file_name: {
                "name": file_name,
            }
        }

        for i, item in enumerate(data, start=1):
            if not isinstance(item, tuple) or len(item) != 3:
                raise ValueError("Each item in data must be a tuple of length 3")
            subquery, response, image = item
            yaml_data[file_name][f"res_{i}"] = [subquery, response, image if image else None] # type: ignore

        # Save the data to a YAML file
        dest_path = self.destination_folder_path / destination_file_path
        try:
            with open(dest_path, "a") as yaml_file:
                yaml.dump(yaml_data, yaml_file, default_flow_style=False)
        except (OSError, IOError) as e:
            self._log_mgr.log_message(
                f"Failed to write to {dest_path}: {e}", "ERROR")

class YAMLHandler:

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



# Parse the YAML data into desired Python objects
def parse_yaml_to_objects(yaml_data: dict, required_name: str) -> (str, List[Tuple]):
    """
    Parses a YAML data structure to extract specific objects based on a required name.

    Args:
        yaml_data (dict): The YAML data to parse, structured as a dictionary.
        required_name (str): The name to search for within the YAML data.

    Returns:
        tuple: A tuple containing the filename (str) and a list of tuples, where each tuple
        contains extracted values. If a value is 'null', it is replaced with an empty string.
    """
    results = []
    filename = None

    # Handle multiple "result" entries in the YAML
    for entry in yaml_data:
        if entry.get(required_name, {}).get("name") == required_name:
            filename = entry[required_name]["name"]
            for key in entry[required_name]:
                if key.startswith("res_"):
                    values = entry[required_name][key]
                    # Replace "null" with an empty string
                    results.append((values[0], values[1], values[2] if values[2] is not None else ""))
            break  # Stop once a matching result is found

    return filename, results


def read_results_from_yaml(file_path: str, filename: str) -> List[Tuple]:
    """
    Reads results from a YAML file and parses them into a list of tuples.

    Args:
        file_path (str): The path to the YAML file to be read.
        filename (str): The name used to identify the specific data within the YAML file.

    Returns:
        List[Tuple]: A list of tuples containing the parsed results.
    """
    # Read and parse the YAML file
    yaml_data = read_yaml(os.path.join("outputs", file_path))
    filename, results = parse_yaml_to_objects([yaml_data], filename)

    return results


def load_prompts(prompt: str, file_path="prompts.yaml") -> str:
    """
    Load a specific prompt from a YAML file.

    Args:
        prompt (str): The key of the prompt to retrieve from the YAML file.
        file_path (str, optional): The path to the YAML file containing prompts.
            Defaults to "prompts.yaml".

    Returns:
        str: The prompt data associated with the specified key.

    Raises:
        KeyError: If the specified prompt key is not found in the YAML file.
    """
    with open(file_path, 'r') as f:
        prompts = yaml.safe_load(f)
        return prompts[prompt]