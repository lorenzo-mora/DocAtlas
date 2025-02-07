import importlib
from typing import Any, Dict, List, Literal, Tuple, get_args, get_origin

from logger.setup import LoggerManager

logger_manager = LoggerManager(module_name=__name__, project_name="docatlas", console_message_format='%(asctime)s | %(levelname)s --> %(message)s')
logger_manager.setup_logger()

class ConfigurationError(Exception):
    """Exception raised for errors in the configuration validation."""
    def __init__(self, message: str):
        super().__init__(message)

def validate_type(value: Any, expected_type: Any, key_path: str) -> List[str]:
    """Recursively validate a value against an expected type.

    Parameters
    ----------
    value : Any
        The actual value to check.
    expected_type : Any
        The expected type (can be complex like Dict, List, Tuple, Literal).
    key_path : str
        A string representing the hierarchical key path (for detailed errors).

    Returns
    -------
    List[str]
        A list of validation error messages.
    """
    errors = []
    if expected_type is None:
        return errors
    origin = get_origin(expected_type)  # Extract generic type (e.g., List, Dict, Tuple)
    args = get_args(expected_type)  # Extract generic type arguments

    # Case 1: Expected a dictionary with a predefined schema (nested dict check)
    if isinstance(expected_type, dict):
        if not isinstance(value, dict):
            err = f"Incorrect type for '{key_path}': expected Dict, got {type(value)}"
            errors.append(err)
        else:
            for expected_key, expected_value_type in expected_type.items():
                if expected_key not in value:
                    err = f"Missing key '{expected_key}' in '{key_path}'"
                    errors.append(err)
                else:
                    errors.extend(
                        validate_type(
                            value[expected_key],
                            expected_value_type,
                            f"{key_path}['{expected_key}']"
                        )
                    )

    # Case 2: Check for specific allowed values (Literal)
    elif origin is Literal:
        if value not in args:
            err = f"Invalid value for '{key_path}': expected one of {args}, got '{value}'"
            errors.append(err)
    
    # Case 3: Validate lists
    elif origin is list or origin is List:
        if not isinstance(value, list):
            err = f"Incorrect type for '{key_path}': expected List[{args[0]}], got {type(value)}"
            errors.append(err)
        else:
            for i, item in enumerate(value):
                # Recursively check list elements
                errors.extend(
                    validate_type(item, args[0], f"{key_path}[{i}]")
                )

    # Case 4: Validate dictionaries (generic Dict[K, V])
    elif origin is dict or origin is Dict:
        if not isinstance(value, dict):
            err = f"Incorrect type for '{key_path}': expected Dict[{args[0]}, {args[1]}], got {type(value)}"
            errors.append(err)
        else:
            for k, v in value.items():
                # Validate each value in the dict
                errors.extend(
                    validate_type(v, args[1], f"{key_path}['{k}']")
                )

    # Case 5: Validate tuples
    elif origin is tuple or origin is Tuple:
        if not isinstance(value, tuple) or len(value) != len(args):
            err = f"Incorrect format for '{key_path}': expected {expected_type}, got {value}"
            errors.append(err)
        else:
            for i, (item, expected_item_type) in enumerate(zip(value, args)):
                errors.extend(
                    validate_type(item, expected_item_type, f"{key_path}[{i}]")
                )

    # Case 6: Standard types (int, str, float, bool, etc.)
    elif not isinstance(value, expected_type):
        err = f"Incorrect type for '{key_path}': expected {expected_type}, got {type(value)}"
        errors.append(err)

    return errors

def validate_config(module_name: str, schema: Dict[str, Any]):
    """Validate the configuration module against an expected schema.

    Parameters
    ----------
    module_name : str
        The full module path as a string (e.g., "config.processing_text").
    expected_schema : Dict[str, Any]
        A dictionary where keys are expected config variables and values
        are their expected types.
    """
    try:
        config = importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        error_message = f"Configuration module '{module_name}' not found."
        logger_manager.log_message(error_message, "ERROR")
        raise ConfigurationError(error_message) from e

    config_vars = {k: v for k, v in vars(config).items() if not k.startswith("__")}
    errors = []

    # Validate top-level keys
    for key, expected_type in schema.items():
        if key not in config_vars:
            errors.append(f"Missing configuration key: {key}")
        else:
            errors.extend(validate_type(config_vars[key], expected_type, key))

    if errors:
        error_message = f"Validation failed for {module_name}: " + " -- ".join(err for err in errors)
        logger_manager.log_message(error_message, "ERROR")
        raise ConfigurationError(error_message)

    # Log validation results
    logger_manager.log_message(
        f"{chr(0x2705)} Validation passed for `{module_name}`.", "DEBUG")
