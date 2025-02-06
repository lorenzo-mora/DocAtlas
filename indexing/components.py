from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import pymupdf

from config.file_management import TEXT_BOUNDARIES_PAGE
from utils import format_index_with_padding

@dataclass(frozen=True)
class ContextualQA:
    """Represents a set of questions with their context and answers.

    Attributes:
    id : str
        Unique identifier for the completion.
    context : str
        Contextual information related to the questions.
    questions : List[str]
        List of questions.
    answers : List[str]
        List of answers corresponding to the questions.
    """
    id: str
    context: str
    questions: List[str]
    answers: List[str]

    @classmethod
    def from_dict(cls, content: Dict[str, Any]) -> 'ContextualQA':
        """Creates a `ContextualQA` instance from a dictionary.
        
        Raises a ValueError if required fields are missing or TypeError
        if fields have incorrect types.
        """
        missing_fields = [
            field for field in ["completion_id", "context", "questions", "answers"]
            if field not in content]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        if (not isinstance(content["completion_id"], str) or
            not isinstance(content["context"], str)):
            raise TypeError("Fields 'completion_id' and 'context' must be strings.")

        if (not isinstance(content["questions"], list) or
            not isinstance(content["answers"], list)):
            raise TypeError("Fields 'questions' and 'answers' must be lists.")

        return cls(
            id=content["completion_id"],
            context=content["context"],
            questions=content["questions"],
            answers=content["answers"]
        )

    def __str__(self):
        return f'Completion {self.id}'

    def __repr__(self):
        return f'{self.id}: \"{self.questions}\" [\"{self.answers}\"]'

class TextChunk:
    """Represents a chunk of text with associated metadata and methods
    for serialization and representation.

    Attributes
    ----------
    id : str
        Unique identifier for the text chunk.
    raw_content : str
        The original text content.
    processed_content : str
        The processed version of the text content.
    embedding : List[float]
        A list representing the embedding of the text content.

    Methods
    -------
    `serialize_content(raw=False, processed=False, embedding=False)` -> Dict[str, Any]
        Retrieve specified content from the TextChunk instance."""

    processed_content: str = ""
    embedding: List[float] = []

    def __init__(self, id: str, content: str) -> None:
        self.id = id
        self.raw_content = content

    def serialize_content(
            self,
            raw: bool = False,
            processed: bool = False,
            embedding: bool = False
        ) -> Dict[str, Any]:
        """Retrieve specified content from the TextChunk instance.

        Parameters
        ----------
        raw : bool, optional
            If True, include raw content in the output. By default False.
        processed : bool, optional
            If True, include processed content in the output. By default
            False.
        embedding : bool, optional
            If True, include the embedding of the content in the output.
            By default False.

        Returns
        -------
        Dict[str, Any]
            A dictionary containing the requested content types
            with keys 'raw', 'processed', and 'embedding'. Each key maps
            to the corresponding content or None if not requested.
        """
        return {
            "raw": self.raw_content if raw else None,
            "processed": self.processed_content if processed else None,
            "embedding": self.embedding if embedding else None
        }

    def __len__(self) -> int:
        return len(self.raw_content)

    def __str__(self):
        return self.raw_content

    def __repr__(self):
        attributes = [
            attr for attr in ["raw_content", "processed_content", "embedding"]
            if getattr(self, attr, None)
        ]

        formatted_attrs = " and ".join(
            [", ".join(attributes[:-1]), attributes[-1]] if len(attributes) > 1 else attributes
        ) or "none"

        return f"{self.__class__} at {hex(id(self))} with attributes {formatted_attrs} valued"
        

class Page:
    """It represents a page of a document and collects blocks of text
    within the specified boundaries.

    Attributes
    ----------
    number : int
        The page number.
    content :
        The content of the page, expected to have an `artbox` attribute
        and a `get_text` method.
    chunks : list of str
        A list of text blocks extracted from the page content within the
        defined boundaries.
    processed_text : list of string
        The list of paragraphs extracted from the page and elaborated.
    """
    processed_text: List[str] = []

    def __init__(self, number: int, content: pymupdf.Page) -> None:
        self.number = number
        self.content = content
        self.chunks = self.extract_paragraphs()

    def extract_paragraphs(self) -> List[TextChunk]:
        """Extracts paragraphs from the page content within calculated
        boundaries.

        Returns
        -------
        list of str
            A list of non-empty text blocks extracted from the page
            content.
        """
        w, h = self.content.artbox.bottom_right

        boundaries = self.calculate_boundaries(w, h)
        chunks: List[TextChunk] = []
        for i, block in enumerate(self.content.get_text(option="blocks", clip=boundaries)): # type: ignore
            if block[4].strip():
                # fmt_num = format_index_with_padding(i, len(str(len(self))))
                chunks.append(TextChunk(
                    id=f"{self.number}_{i}",
                    content=block[4]
                ))
        return chunks

    def calculate_boundaries(
            self,
            width: float,
            height: float
        ) -> Tuple[float, float, float, float]:
        """Calculate the boundaries of the text area on the page.

        Parameters
        ----------
        width : float
            The width of the page.
        height : float
            The height of the page.

        Returns
        -------
        Tuple[float, float, float, float]
            A tuple representing the left, top, right, and bottom
            boundaries of the text area, calculated as a fraction of the
            page dimensions.
        """
        return (
            width * TEXT_BOUNDARIES_PAGE["x"][0],
            height * TEXT_BOUNDARIES_PAGE["y"][0],
            width * TEXT_BOUNDARIES_PAGE["x"][1],
            height * TEXT_BOUNDARIES_PAGE["y"][1]
        )

    def get_serialized_content(
            self,
            raw_chunks: bool = False,
            processed_chunks: bool = False,
            embedded_chunks: bool = False,
            flatten: bool = True,
            exclude_empty: bool = False
        ) -> Dict[str, Any]:
        """Retrieves serialized content from the page's text chunks
        based on specified chunk types.

        Parameters
        ----------
        raw_chunks : bool, optional
            If True, include raw text chunks in the output. By default
            False.
        processed_chunks : bool, optional
            If True, include processed text chunks in the output. By
            default False.
        embedded_chunks : bool, optional
            If True, include embedded text chunks in the output. By
            default False.
        flatten : bool, optional
            If True, flatten the serialized content by adding the page
            number to each chunk's data. By default True.
        exclude_empty : bool, optional
            If True, exclude chunks without embeddings from the output.
            By default False.

        Returns
        -------
        Dict[str, Any]
            A dictionary mapping chunk indices to their respective
            content, filtered by the specified chunk types.
        """
        id_length = len(str(len(self)))
        keys = [format_index_with_padding(i, id_length) for i in range(len(self.chunks))]

        # values = [
        #     {**chunk.serialize_content(raw_chunks, processed_chunks, embedded_chunks), "page": self.number}
        #     if flatten else chunk.serialize_content(raw_chunks, processed_chunks, embedded_chunks)
        #     for chunk in self.chunks if chunk.embedding or not exclude_empty
        # ]
        values = []
        for chunk in self.chunks:
            if chunk.embedding or not exclude_empty:
                try:
                    serialized_content = chunk.serialize_content(
                        raw_chunks, processed_chunks, embedded_chunks)
                    if flatten:
                        serialized_content["page"] = self.number
                    values.append(serialized_content)
                except Exception as e:
                    # Log the exception as needed
                    continue

        return {key: value for key, value in zip(keys, values)}

    def __len__(self) -> int:
        return len(self.chunks)

    def __str__(self):
        return f'{"| ".join(str(chk) for chk in self.chunks)}'

    def __repr__(self):
        return str(self.content)

@dataclass
class DocInfo:
    """A data class representing document information with methods to
    create an instance from a dictionary.

    Attributes
    ----------
    id : str
        The unique identifier of the document.
    title : str
        The title of the document.
    embed_link : str
        The embed link of the document.

    """
    id: str
    title: str
    embed_link: str

    @classmethod
    def from_dict(cls, info: Dict[str, Any]) -> 'DocInfo':
        """Creates a `DocInfo` instance from a dictionary.
        
        Raises a ValueError if required fields are missing.
        """
        if "file_id" not in info or "title" not in info:
            raise ValueError("Missing required fields: 'file_id' and/or 'title'")

        return cls(
            id=info["file_id"],
            title=info["title"],
            embed_link=info.get("embedLink", None) or info.get("link", None)
        )

    def __str__(self):
        return f'{self.id} - {self.title}'

    def __repr__(self):
        return f"{self.__class__} at {hex(id(self))} of \"{self.embed_link}\""

class Document:
    """It represents a document composed of multiple pages and
    associated metadata.

    Attributes
    ----------
    pages : List[Page]
        A list of Page objects representing the pages of the document.
    metadata : DocInfo
        An instance of DocInfo containing metadata about the document.
    """

    def __init__(self, pages: List[Page], info: DocInfo) -> None:
        if (not isinstance(pages, list) or
            not all(isinstance(page, Page) for page in pages)):
            raise ValueError("`pages` must be a list of `Page` objects.")
        if not isinstance(info, DocInfo):
            raise ValueError("`metadata` must be an instance of `DocInfo`.")

        self.pages = pages
        self.metadata = info

    @classmethod
    def from_dict(cls, file_content: Dict[str, Any]) -> 'Document':
        """Creates a `Document` instance from a dictionary containing
        page and metadata information.

        Raises a ValueError if required fields are missing.
        """
        if "pages" not in file_content or "info" not in file_content:
            raise ValueError("Missing required keys: 'pages' and/or 'info'")

        pages = cls.extract_pages(file_content)
        info = cls.extract_info(file_content)
        return cls(pages=pages, info=info)

    @staticmethod
    def extract_pages(file_content: Dict[str, Any]) -> List[Page]:
        """Extracts a list of `Page` objects from the provided dictionary."""
        return file_content.get("pages", [])

    @staticmethod
    def extract_info(file_content: Dict[str, Any]) -> DocInfo:
        """Extracts `DocInfo` from the provided dictionary."""
        return DocInfo.from_dict(file_content.get("info", {}))

    def serialize(
            self,
            raw_content: bool = True,
            processed_content: bool = False,
            content_embedding: bool = False,
            keep_structure: bool = False,
            exclude_missing_embeddings: bool = False
        ) -> Dict[str, Any]:
        """Serializes the document into a dictionary format.

        Parameters
        ----------
        raw_content : bool, optional
            If True, includes raw content of each page in the
            serialization. By default True.
        processed_content : bool, optional
            If True, includes processed content of each page in the
            serialization. By default False.
        content_embedding : bool, optional
            If True, includes the embeddings of the content of each page
            in the serialization. By default False.
        keep_structure : bool, optional
            If True, keeps the `Document.Page.TextChunk` structure
            in the serialization, otherwise flattens the content by
            excluding the page level (information retrievable directly
            from the chunk itself). By default False.
        exclude_missing_embeddings : bool, optional
            If True, excludes chunks without embeddings from the
            serialization. By default False.

        Returns
        -------
        Dict[str, Any]
            A dictionary containing the document's metadata and
            serialized pages.
        """
        content_pages: Dict[str, Any] = {}
        if keep_structure:
            # Maintain the structure Document.Page.TextChunk
            id_length = len(str(self.__len__()))
            for i, page in enumerate(self.pages):
                current_content = page.get_serialized_content(
                    raw_content,
                    processed_content,
                    content_embedding,
                    flatten=False,
                    exclude_empty=exclude_missing_embeddings
                )
                if not current_content:
                    continue

                content_pages[
                    format_index_with_padding(i, id_length)] = current_content

        else:
            # Flatten the structure of the pages
            number_of_chunks = sum(len(page) for page in self.pages)
            id_length = len(str(number_of_chunks))
            lag_id = 0
            for page in self.pages:
                current_content = page.get_serialized_content(
                    raw_content,
                    processed_content,
                    content_embedding,
                    flatten=True,
                    exclude_empty=exclude_missing_embeddings
                )
                if not current_content:
                    continue

                for chk_id, chk in current_content.items():
                    content_pages[
                        format_index_with_padding(int(chk_id) + lag_id, id_length)
                    ] = chk
                lag_id += len(page)

        return {
            "id": getattr(self.metadata, 'id', '<ID>'),
            "name": getattr(self.metadata, 'title', '<TITLE>'),
            "location": getattr(self.metadata, 'embed_link', '<SOURCE_PATH>'),
            "content": content_pages
        }

    def __len__(self) -> int:
        return len(self.pages)

    def __str__(self):
        return f'{self.metadata}: {self.pages}'
