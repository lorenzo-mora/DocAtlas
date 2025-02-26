from pathlib import Path
import shutil
from typing import List, Optional, Set, Tuple, Union

import fitz
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

from config.file_management import OVERWRITE_IF_EXISTS, UNIQUE_IF_EXISTS
from logger.setup import LoggerHandler
from text.components import DocInfo
from text.utils import UUIDManager


logger = LoggerHandler().get_logger(__name__)

class Uploader:

    docs_info: List[DocInfo]
    _unavbl_uuids: Set[str]

    def __init__(
            self,
            folder_path: Union[str, Path]
        ) -> None:
        assert isinstance(folder_path, (str, Path)), "The `folder_path` must be a string or a Path"

        self.source_folder_path = self._validate_data_source_folder(folder_path)

        self._unavbl_uuids = set()
        self.docs_info = []

        logger.debug(
            f"Successfully initialised the {self.__class__.__name__} instance."
        )

    @property
    def unavailable_uuids(self) -> Optional[Set[str]]:
        """Unique identifiers cannot be assigned to a new document."""
        return self._unavbl_uuids if self._unavbl_uuids else None

    @unavailable_uuids.setter
    def unavailable_uuids(self, ids: Union[List[str], str]) -> None:
        if not isinstance(ids, (list, str)):
            raise TypeError(
                ("`ids` may be either a list of strings or a string. "
                    f"Instead, a {type(ids)} has been provided.")
            )

        if isinstance(ids, str):
            self._unavbl_uuids.add(ids)
        elif isinstance(ids, list):
            self._unavbl_uuids.update(ids)

    def download_drive_folder_to_local(self, folder_id: str) -> None:
        """Download files from a specified Google Drive folder to a
        local folder.

        Parameters
        ----------
        folder_id : str
            The ID of the Google Drive folder.
        """
        # Authenticate with Google Drive
        gauth = GoogleAuth()
        gauth.LoadCredentialsFile("credentials/credentials.json")

        if gauth.credentials is None:
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            gauth.Refresh()
        else:
            # Initialize the saved creds
            gauth.Authorize()

        # Save the current credentials to a file
        gauth.SaveCredentialsFile("credentials/credentials.json")

        drive = GoogleDrive(gauth)

        # List files in the specified Google Drive folder
        file_list = drive.ListFile({'q': f"'{folder_id}' in parents and trashed=false"}).GetList()

        # Initialize a list to store information about new files
        new_files = []
        logger.debug("Downloading files from Google Drive...")

        # Iterate through each file in the list
        for file in file_list:
            # Check if the file already exists locally
            local_file_path = self.source_folder_path / file["title"]

            if not local_file_path.is_file():
                # Download the file content and save it to the local folder
                file.GetContentFile(local_file_path)

                # Append information about the downloaded file to the list
                new_files.append(DocInfo.from_dict(file))

        # Print the list of newly downloaded files
        if len(new_files) == 0:
            logger.debug("No new files were downloaded.")
            return
        
        logger.debug(f"{len(new_files)} new file(s) were detected.")
        logger.debug("- ".join([
            f"Doc {i} => name: {f["title"]}, id: {f["id"]} "
            for i, f in enumerate(new_files)
        ]))

        self.docs_info.extend(new_files)

    def get_pdf_from_local(
            self,
            file_path: Union[str, Path],
            force: bool = OVERWRITE_IF_EXISTS,
            unique: bool = UNIQUE_IF_EXISTS
        ) -> Optional[Path]:
        """Create a symbolic link for a PDF file from a local path to
        the source folder.

        Parameters
        ----------
        file_path : str or Path
            The path to the PDF file to be linked.
        force : bool, optional
            If True, overwrites the existing file. If False, skips if
            the file exists. Defaults to the value of
            `OVERWRITE_IF_EXISTS`.
        unique : bool, optional
            If True and `force=False`, adds an incremental number to the
            filename if a file with the same name exists. Otherwise, the
            file is not linked into the project folder. By default False.

        Returns
        -------
        Optional[Path]
            The path to the created symbolic link, or None if the link
            was not created due to conflicts.

        Raises
        ------
        ValueError
            If the specified path is not a file or is not a PDF.
        FileNotFoundError
            If the file does not exist.
        PermissionError
            If there are permission issues with the file or destination.
        Exception
            For any unexpected errors during symlink creation.
        """
        file_path = Path(file_path)

        if not file_path.is_file():
            raise ValueError(
                "Specified path is empty or does not point to a file")

        if file_path.suffix.lower() != ".pdf":
            logger.warning(f"`{file_path.name}` file is not a PDF; skipping.")
            return

        dest_path = self.source_folder_path / file_path.name

        # Handle file existence logic
        if dest_path.exists() or dest_path.is_symlink():
            if force:
                logger.warning(f"Overwriting `{dest_path.name}`.")
                dest_path.unlink()  # Remove existing file/symlink
            elif unique:
                _, dest_path = self._get_unique_file_path(dest_path)
                logger.debug(
                    f"Saving file as `{dest_path.name}` to avoid conflict.")
            else:
                logger.warning(
                    f"File `{dest_path.name}` already exists; skipping link creation.")
                return None

        # Create symbolic link instead of copying
        try:
            # with open(file_path, 'rb') as src, open(dest_path, 'wb') as dst:
            #     shutil.copyfileobj(src, dst)
            dest_path.hardlink_to(file_path)
            logger.debug(f"Symbolic link created: `{dest_path}` → `{file_path}`")
        except FileNotFoundError as e:
            logger.error(f"File not found: `{file_path}`. Error: {e}")
            raise
        except PermissionError as e:
            logger.error(
                f"Permission denied for `{file_path}` or `{dest_path}`. Error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating symlink `{dest_path}`: {e}")
            raise

        info = self._get_metadata(dest_path)
        self.docs_info.append(info)
        return dest_path

    def get_all_pdf_from_local_folder(
            self,
            folder_path: Union[str, Path]
        ) -> List[str]:
        """Retrieve all PDF files from a specified local folder and
        process them.

        Parameters
        ----------
        folder_path : str or Path
            The path to the local folder containing PDF files.

        Raises
        ------
        ValueError
            If the specified path does not exist or does not point to a
            folder.
        """
        folder_path = Path(folder_path)

        if not folder_path.is_dir():
            raise ValueError(
                "Specified path does not exist or does not point to a folder")

        pdf_files = [child for child in folder_path.iterdir() if child.is_file()]
        compatible_files = []
        for pdf_file in pdf_files:
            dest = None
            try:
                dest = self.get_pdf_from_local(pdf_file)
            except Exception as e:
                logger.warning(
                    f"The file `{pdf_file}` is skipped due to an error: {e}")
            if dest:
                compatible_files.append(dest)

        logger.info(
            (f"Successfully retrieved the content of folder `{folder_path}`: "
             f"{len(compatible_files)} new file(s) detected."))
        return compatible_files

    def _validate_data_source_folder(self, path: Union[str, Path]) -> Path:
        path = Path(path)
        if path.exists() and not path.is_dir():
            raise ValueError("Specified path does not point to a folder")

        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

        return path

    def _get_unique_file_path(self, destination_path: Path) -> Tuple[str, Path]:
        """Generate a unique file path by appending a counter to the
        file name if a file with the same name already exists in the
        destination folder.

        Parameters
        ----------
        destination_path : Path
            The initial path where the file is intended to be saved.

        Returns
        -------
        Tuple[str, Path]
            A tuple containing the unique file name and the
            corresponding unique file path.
        """
        base_name = destination_path.stem
        ext = destination_path.suffix
        file_name = destination_path.name
        dest_folder = destination_path.parent
        dest_path = destination_path

        existing_files = set(p.name for p in dest_folder.iterdir())
        counter = 1
        while file_name in existing_files:
            logger.warning(
                f"`{file_name}` file already exists in the destination.")
            file_name = f"{base_name}_{counter}{ext}"
            dest_path = dest_folder.joinpath(file_name)
            counter += 1
        return file_name, dest_path

    def _get_metadata(self, file_path: Union[str, Path]) -> DocInfo:
        """Extract metadata from a PDF file and return it as a DocInfo object."""
        file_path = Path(file_path).resolve(strict=True)
        try:
            with fitz.open(file_path) as doc:
                metadata = doc.metadata
        except (FileNotFoundError, fitz.FileDataError) as e:
            logger.error(f"Error opening file `{file_path}`: {e}")
            raise
        metadata = metadata or {}

        return DocInfo(
            id=UUIDManager.uuid(self.unavailable_uuids),
            file_name=file_path.name,
            title=metadata.get("title", ""),
            author=metadata.get("author", ""),
            subject=metadata.get("subject", ""),
            keywords=metadata.get("keywords", ""),
            embed_link=metadata.get("file_path", str(file_path))
        )