from pathlib import Path
import shutil
from typing import List, Optional, Tuple, Union

import fitz
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
import pymupdf

from config.file_management import PDF_SOURCE_FOLDER
from indexing.components import DocInfo, Document, Page
from indexing.utils import UUIDManager
from logger.setup import LoggerManager


class FileManager:

    docs_info: List[DocInfo]
    docs: List[Document]

    def __init__(
            self,
            logger_manager: LoggerManager,
            folder_path: Union[str, Path] = PDF_SOURCE_FOLDER
        ) -> None:
        self._log_mgr = logger_manager
        self.source_folder_path = self._validate_data_source_folder(folder_path)

        self.docs_info = []
        self.docs = []

        self._log_mgr.log_message(
            f"Successfully initialised the {self.__class__.__name__} instance.",
            "DEBUG"
        )

    def _validate_data_source_folder(self, path: Union[str, Path]) -> Path:
        path = Path(path)

        if path.exists() and not path.is_dir():
            raise ValueError("Specified path does not point to a folder")

        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

        return path

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
        self._log_mgr.log_message(
            "Downloading files from Google Drive...", "DEBUG")

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
            self._log_mgr.log_message("No new files were downloaded.", "DEBUG")
            return
        
        self._log_mgr.log_message(
            f"{len(new_files)} new file(s) were detected.", "DEBUG")
        self._log_mgr.log_message(
            "- ".join([
                f"Doc {i} => name: {f["title"]}, id: {f["id"]} "
                for i, f in enumerate(new_files)
            ]), "DEBUG")

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
            self._log_mgr.log_message(
                f"`{file_name}` file already exists in the destination.",
                "WARNING")
            file_name = f"{base_name}_{counter}{ext}"
            dest_path = dest_folder.joinpath(file_name)
            counter += 1
        return file_name, dest_path

    def get_pdf_from_local(
            self,
            file_path: Union[str, Path],
            force: bool = False
        ) -> Optional[Path]:
        """Copies a PDF file from a specified local path to the source
        folder.

        Parameters
        ----------
        file_path : str or Path
            The path to the local file to be copied.
        force : bool, optional
            If True, overwrites the file in the destination if it
            exists. By default False.

        Raises
        ------
        ValueError
            If the specified path is empty or does not point to a file.
        """
        file_path = Path(file_path)

        if not file_path.is_file():
            raise ValueError(
                "Specified path is empty or does not point to a file")

        file_name = file_path.name
        dest_path = self.source_folder_path / file_name

        if file_path.suffix.lower() != ".pdf":
            self._log_mgr.log_message(
                f"`{file_name}` file is not a PDF; it is skipped.", "WARNING")
            return

        if not force:
            file_name, dest_path = self.get_unique_file_path(dest_path)

        try:
            with open(file_path, 'rb') as src, open(dest_path, 'wb') as dst:
                shutil.copyfileobj(src, dst)
        except FileNotFoundError as e:
            self._log_mgr.log_message(
                f"File not found: `{file_path}`. Error: {e}", 
                "ERROR"
            )
        except PermissionError as e:
            self._log_mgr.log_message(
                f"Permission denied when accessing `{file_path}` or `{dest_path}`. Error: {e}", 
                "ERROR"
            )
        except Exception as e:
            self._log_mgr.log_message(
                f"Unexpected error copying file `{file_path}` to `{dest_path}`: {e}", 
                "ERROR"
            )

        self._log_mgr.log_message(
            f"File `{file_path}` was successfully saved in the current folder (`{dest_path}`).",
            "DEBUG")

        info = DocInfo(
            id=UUIDManager.uuid(), title=file_name, embed_link=str(file_path))
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
            dest = self.get_pdf_from_local(pdf_file)
            if dest:
                compatible_files.append(dest)

        self._log_mgr.log_message(
            (f"Successfully retrieved the contents of folder `{folder_path}` "
             f"({len(compatible_files)} file(s)) in the current folder."),
            "DEBUG")
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
            self._log_mgr.log_message(
                f"File `{file_info.title}` is not a PDF; processing skipped.",
                "ERROR"
            )
            return

        self._log_mgr.log_message(
            f"File name: {file_info.title}, id: {file_info.id}", "DEBUG")

        pdf_path = self.source_folder_path.joinpath(file_info.title)
        try:
            doc = pymupdf.open(pdf_path)
            self._log_mgr.log_message(
                f"Number of pages: {len(doc)}", "DEBUG")

            pages = [
                Page(i, content=page)
                for i, page in enumerate(doc) # type: ignore
            ]

            self.docs.append(Document(pages, info=file_info))
        except FileNotFoundError:
            self._log_mgr.log_message(
                f"File not found: {pdf_path}", "ERROR")
        except fitz.FileDataError:
            self._log_mgr.log_message(
                f"Corrupted PDF file: {pdf_path}", "ERROR")
        except Exception as e:
            self._log_mgr.log_message(
                f"Unexpected error processing file `{pdf_path}`: {e}", "ERROR")