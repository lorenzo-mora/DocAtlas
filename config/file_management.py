# The local directory path where downloaded data will be saved.
from typing import Dict, Tuple


PDF_SOURCE_FOLDER: str = "./data"

# The margins of the text on the page, expressed as a relative
# percentage in a dictionary with `x` and `y` as the key and a tuple
# representing the minimum and maximum for the relative axis.
TEXT_BOUNDARIES_PAGE: Dict[str, Tuple[float, float]] = dict(
    x = (0.05, 0.95),
    y = (0.06, 0.94)
)

file_to_extract: str = r"C:\Users\l.mora\Downloads\papers"