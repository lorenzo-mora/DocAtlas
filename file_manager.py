from pathlib import Path
import shutil
from typing import Any, Dict, List, Union

import pandas as pd
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from PyPDF2 import PdfReader

from logger.setup import LoggerManager
import config
from utils import UUIDManager


class FileInfo:

    def __init__(self, file_id: str, title: str, link: str) -> None:
        self.id = file_id
        self.title = title
        self.embedLink = link

    @classmethod
    def from_dict(cls, metadata: Dict[str, Any]):
        return cls(
            file_id=metadata.get("file_id", None),
            title=metadata.get("title", None),
            link=metadata.get("embedLink", None) or metadata.get("link", None)
        )

class FileManager:

    def __init__(
            self,
            logger_manager: LoggerManager,
            folder_path: Union[str, Path] = config.PDF_SOURCE_FOLDER
        ) -> None:
        self._log_mgr = logger_manager
        self.source_folder_path = self._validate_data_source_folder(folder_path)

        self.files: List[FileInfo] = []
        self.content: pd.DataFrame = pd.DataFrame(
            columns=["file_id", "file_name", "file_link", "page_number", "text"])

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
                new_files.append(FileInfo.from_dict(file))

        # Print the list of newly downloaded files
        if len(new_files) == 0:
            self._log_mgr.log_message("No new files were downloaded.", "DEBUG")
            return
        
        self._log_mgr.log_message(
            f"{len(new_files)} new files were detected.", "DEBUG")
        self._log_mgr.log_message(
            "- ".join([
                f"Doc {i} => name: {f["title"]}, id: {f["id"]} "
                for i, f in enumerate(new_files)
            ]), "DEBUG")

        self.files.extend(new_files)

    def get_file_from_local(
            self,
            file_path: Union[str, Path],
            force: bool = False
        ) -> None:
        file_path = Path(file_path)

        if not file_path.is_file():
            raise ValueError(
                "Specified path is empty or does not point to a file")

        base_name = file_path.stem
        ext = file_path.suffix
        file_name = file_path.name
        dest_path = self.source_folder_path / file_name

        if ext not in (".pdf", ".PDF"):
            self._log_mgr.log_message(
                f"`{file_name}` file is not a PDF; it is skipped.", "WARNING")
            return

        if dest_path.exists() and not force:
            self._log_mgr.log_message(
            f"`{file_name}` file already exists in the destination.",
            "WARNING")
            i = 1
            file_name = f"{base_name}_{i}{ext}"
            dest_path = self.source_folder_path.joinpath(file_name)
            while dest_path.exists():
                self._log_mgr.log_message(
                f"`{file_name}` file already exists in the destination.",
                "WARNING")
                i+=1
                file_name = f"{base_name}_{i}{ext}"
                dest_path = self.source_folder_path.joinpath(file_name)

        shutil.copy(file_path, dest_path)

        self._log_mgr.log_message(
            f"File `{file_path}` was successfully saved in the current folder (`{dest_path}`).",
            "DEBUG")

        info = FileInfo(
            file_id=UUIDManager.uuid(), title=file_name, link=str(file_path))
        self.files.append(info)

    def get_all_from_local_folder(self, folder_path: Union[str, Path]) -> None:
        folder_path = Path(folder_path)

        if not folder_path.is_dir():
            raise ValueError(
                "Specified path does not exist or does not point to a folder")

        i = 0
        for child in folder_path.iterdir():
            if child.is_file():
                self.get_file_from_local(child)
                i+=1

        self._log_mgr.log_message(
            (f"Successfully retrieved the contents of folder `{folder_path}` "
             f"({i} file(s)) in the current folder."),
            "DEBUG")

    def process_pdf_file(
            self,
            file_info: FileInfo
        ):
        if file_info.title.split('.')[-1] == 'pdf':
            self._log_mgr.log_message(
                f"File name: {file_info.title}, id: {file_info.id}", "DEBUG")

            pdf_path = self.source_folder_path.joinpath(file_info.title)
            pdf_reader = PdfReader(pdf_path)
            self._log_mgr.log_message(
                f"Number of pages: {len(pdf_reader.pages)}", "DEBUG")
            
            for i, page in enumerate(pdf_reader.pages):
                self.content.loc[len(self.content)] = [
                    file_info.id,
                    file_info.title,
                    file_info.embedLink,
                    i+1,
                    page.extract_text()
                ]