from pathlib import Path
import shutil
from typing import List, Optional, Set, Tuple, Union

import fitz
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import pymupdf

from config.file_management import PDF_SOURCE_FOLDER, OVERWRITE_IF_EXISTS, UNIQUE_IF_EXISTS
from indexing.components import DocInfo, Document, Page
from indexing.utils import UUIDManager
from logger.setup import LoggerHandler


logger = LoggerHandler().get_logger(__name__)

class PDFHandler:

    docs_info: List[DocInfo]
    docs: List[Document]
    _unavbl_uuids: Set[str]

    def __init__(
            self,
            folder_path: Union[str, Path] = PDF_SOURCE_FOLDER
        ) -> None:
        self.source_folder_path = self._validate_data_source_folder(folder_path)

        self._unavbl_uuids = set()
        self.docs_info = []
        self.docs = []

        logger.debug(
            f"Successfully initialised the {self.__class__.__name__} instance."
        )

    def _validate_data_source_folder(self, path: Union[str, Path]) -> Path:
        path = Path(path)

        if path.exists() and not path.is_dir():
            raise ValueError("Specified path does not point to a folder")

        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

        return path

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

    def get_unique_file_path(self, destination_path: Path) -> Tuple[str, Path]:
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

    def get_pdf_from_local(
            self,
            file_path: Union[str, Path],
            force: bool = OVERWRITE_IF_EXISTS,
            unique: bool = UNIQUE_IF_EXISTS
        ) -> Optional[Path]:
        """Copies a PDF file from a specified local path to the source
        project folder.

        Parameters
        ----------
        file_path : str or Path
            The path to the local file to be copied.
        force : bool, optional
            If True, overwrites the existing file. If False, skips if
            the file exists. By default False.
        unique : bool, optional
            If True and `force=False`, adds an incremental number to the
            filename if a file with the same name exists. Otherwise, the
            file is not copied into the project folder. By default False.

        Raises
        ------
        ValueError
            If the specified path is empty or does not point to a file.
        """
        file_path = Path(file_path)

        if not file_path.is_file():
            raise ValueError(
                "Specified path is empty or does not point to a file")

        if file_path.suffix.lower() != ".pdf":
            logger.warning(
                f"`{file_path.name}` file is not a PDF; it is skipped.")
            return

        dest_path = self.source_folder_path / file_path.name
        # Handle file existence logic
        if dest_path.exists():
            if force:
                logger.warning(f"Overwriting `{dest_path.name}`.")
            elif unique:
                _, dest_path = self.get_unique_file_path(dest_path)
                logger.debug(
                    f"Saving file as `{dest_path.name}` to avoid conflict."
                )
            else:
                logger.warning(
                    f"File `{dest_path.name}` already exists; skipping copy.")
                return None

        # Perform the file copy operation
        try:
            with open(file_path, 'rb') as src, open(dest_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
        except FileNotFoundError as e:
            logger.error(f"File not found: `{file_path}`. Error: {e}")
            raise
        except PermissionError as e:
            logger.error(
                f"Permission denied when accessing `{file_path}` or `{dest_path}`. Error: {e}", 
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error copying file `{file_path}` to `{dest_path}`: {e}", 
            )
            raise

        logger.debug(
            f"File `{file_path.name}` was successfully saved as `{dest_path.name}`.",
        )

        info = DocInfo(
            id=UUIDManager.uuid(self.unavailable_uuids),
            title=dest_path.name,
            embed_link=str(file_path)
        )
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

    def process_pdf_file(
            self,
            file_info: DocInfo
        ) -> None:
        """Process a PDF file by opening it, extracting its pages, and
        appending the document to the internal list of documents.


        Parameters
        ----------
        file_info : DocInfo
            Information about the file to be processed, including its
            title and ID.

        Raises
        ------
        FileNotFoundError
            If the specified PDF file is not found in the source folder.
        fitz.FileDataError
            If the PDF file is corrupted and cannot be opened.
        Exception
            For any unexpected errors during the processing of the PDF
            file.
        """
        if file_info.title.split('.')[-1].casefold() != 'pdf':
            logger.error(
                f"File `{file_info.title}` is not a PDF; processing skipped.")
            return

        logger.debug(f"File name: {file_info.title}, id: {file_info.id}")

        pdf_path = self.source_folder_path.joinpath(file_info.title)
        try:
            doc = pymupdf.open(pdf_path)
            logger.debug(f"Number of pages: {len(doc)}")

            pages = [
                Page(i, content=page)
                for i, page in enumerate(doc) # type: ignore
            ]

            self.docs.append(Document(pages, info=file_info))
        except FileNotFoundError:
            logger.error(f"File not found: {pdf_path}")
        except fitz.FileDataError:
            logger.error(f"Corrupted PDF file: {pdf_path}")
        except Exception as e:
            logger.error(f"Unexpected error processing file `{pdf_path}`: {e}")
