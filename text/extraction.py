from pathlib import Path
from typing import List, Union

import fitz
import pymupdf

from logger.setup import LoggerHandler
from text.components import DocInfo, Document, Page


logger = LoggerHandler().get_logger(__name__)

class TextExtractor:

    docs: List[Document]

    def __init__(
            self,
            folder_path: Union[str, Path]
        ) -> None:
        assert isinstance(folder_path, (str, Path)), "The `folder_path` must be a string or a Path"

        self.source_folder_path = self._validate_data_source_folder(folder_path)
        self.docs = []

        logger.debug(
            f"Successfully initialised the {self.__class__.__name__} instance."
        )

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
            doc = pymupdf.Document(pdf_path)
            logger.debug(f"Number of pages: {doc.page_count}")

            pages = [
                Page(page_number, page_object=page)
                for page_number, page in enumerate(doc) # type: ignore
            ]

            self.docs.append(Document(pages, info=file_info))
            # doc.close()
        except FileNotFoundError:
            logger.error(f"File not found: {pdf_path}")
        except fitz.FileDataError:
            logger.error(f"Corrupted PDF file: {pdf_path}")
        except Exception as e:
            logger.error(f"Unexpected error processing file `{pdf_path}`: {e}")

    def _validate_data_source_folder(self, path: Union[str, Path]) -> Path:
        path = Path(path)
        if path.exists() and not path.is_dir():
            raise ValueError("Specified path does not point to a folder")

        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)

        return path