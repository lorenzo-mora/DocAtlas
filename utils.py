import re
from typing import Optional


def contains_placeholders(s: str) -> bool:
    """Determine if a string contains placeholders.

    The function checks if the input string contains any of the
    following placeholders:
    - `'%s'`
    - `'{}'`
    - `'{{}}'`

    Parameters
    ----------
    s : str
        The string to be checked for placeholders.

    Returns
    -------
    bool
        True if the string contains any placeholders, False otherwise.
    """
    return bool(re.search(r'(?:%\w|\{\{|\})', s))

def format_index_with_padding(
        raw_index: int,
        desired_length: Optional[int] = None
    ) -> str:
    """Formats an integer index with leading zeros to match a specified
    length.

    Parameters
    ----------
    raw_index : int
        The integer index to be formatted.
    desired_length : int or None, optional
        The desired length of the formatted string. By default None,
        then silently the same length as `raw_index`.

    Returns
    -------
    str
        The formatted index as a string with leading zeros.

    Raises
    ------
    ValueError
        If `raw_index` or `desired_length` are not integers, if
        `raw_index` is negative, if `desired_length` is not positive, or
        if the length of `raw_index` exceeds `desired_length`.

    Example
    -------
    >>> format_index_with_padding(42, 5)
    '00042'
    >>> format_index_with_padding(7)
    '7'
    >>> format_index_with_padding(123, 3)
    '123'
    >>> format_index_with_padding(0, 4)
    '0000'
    """
    desired_length = desired_length or len(str(raw_index))

    if (not isinstance(raw_index, int) or not isinstance(desired_length, int)):
        raise ValueError("Both `raw_index` and `desired_length` must be integers.")
    if raw_index < 0:
        raise ValueError("Index must be non-negative")
    if desired_length <= 0:
        raise ValueError("`desired_length` must be a positive integer.")
    if len(str(raw_index)) > desired_length:
        raise ValueError("`raw_index` length exceeds desired length.")

    return f"{raw_index:0{desired_length}}"

def convert_case(
    input_str: str,
    to_snake_case: bool = False,
    to_camel_case: bool = False
) -> str:
    """Convert a string between `camelCase` and `snake_case` or to a `readable` format.

    Parameters
    ----------
    input_str : str
        The input string to be converted.
    to_snake_case : bool, optional
        If True, convert from camelCase to snake_case, by default False
    to_camel_case : bool, optional
        If True, convert from snake_case to camelCase, by default False

    Returns
    -------
    str
        The converted string.

    Raises
    ------
    TypeError
        If input_str is not a string.
    ValueError
        If both to_snake_case and to_camel_case are True.
    """
    if not isinstance(input_str, str):
        raise TypeError("input_str must be a string")
    if to_snake_case and to_camel_case:
        raise ValueError("Only one of `to_snake_case` or `to_camel_case` can be True.")

    pattern = r'(?<!^)(?=[A-Z])'
    if to_snake_case:
        # Convert camelCase to snake_case
        # return re.sub(r'(?<!^)(?=[A-Z])', '_', input_str).lower()
        return re.sub(pattern, '_', input_str).lower()
    elif to_camel_case:
        # Convert snake_case to camelCase
        words = input_str.split('_')
        return words[0].lower() + ''.join(word.capitalize() for word in words[1:])
    
    # Default: Convert to a readable string
    if '_' in input_str:  # Handle snake_case
        return ' '.join(word.capitalize() for word in input_str.split('_'))
    else:  # Handle camelCase
        readable = re.sub(r'(?<!^)(?=[A-Z])', ' ', input_str)
        return readable.capitalize()