from typing import Dict, Tuple

# The path to the local folder where the downloaded files will be saved.
PDF_SOURCE_FOLDER: str = "./data"

OUTPUT_DESTINATION_FOLDER: str = "./output"

# Overwrite the file in the source folder of the project if a copy
# already exists.
OVERWRITE_IF_EXISTS: bool = False

# In any case, copy the file with an incremental suffix, if a copy
# already exists in the project source folder. `OVERWRITE_IF_EXISTS`
# must be set to False if the copy already present in the folder is to
# be retained.
UNIQUE_IF_EXISTS: bool = False

# The margins of the text on the page, expressed as a relative
# percentage in a dictionary with `x` and `y` as the key and a tuple
# representing the minimum and maximum for the relative axis.
TEXT_BOUNDARIES_PAGE: Dict[str, Tuple[float, float]] = dict(
    x = (0.05, 0.95),
    y = (0.06, 0.94)
)

source_path: str = r"C:\Users\l.mora\Downloads\papers"