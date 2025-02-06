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