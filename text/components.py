from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

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
    context_id: str
    completion_id: str
    # context: str
    questions: List[str]
    answers: List[str]

    @classmethod
    def from_dict(cls, content: Dict[str, Any]) -> 'ContextualQA':
        """Creates a `ContextualQA` instance from a dictionary.
        
        Raises a ValueError if required fields are missing or TypeError
        if fields have incorrect types.
        """
        missing_fields = [
            field for field in ["context_id", "completion_id", "questions", "answers"]
            if field not in content]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        if (not isinstance(content["context_id"], str) or
            not isinstance(content["completion_id"], str)):
            raise TypeError(
                "Fields 'context_id' and 'completion_id' must be strings.")

        if (not isinstance(content["questions"], list) or
            not isinstance(content["answers"], list)):
            raise TypeError("Fields 'questions' and 'answers' must be lists.")

        return cls(
            context_id=content["context_id"],
            completion_id=content["completion_id"],
            # context=content["context"],
            questions=content["questions"],
            answers=content["answers"]
        )

    def __str__(self):
        return f'Completion {self.context_id}'

    def __repr__(self):
        return f'{self.context_id}: \"{self.questions}\" [\"{self.answers}\"]'

@dataclass
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float
    x0_norm: Optional[float] = None
    y0_norm: Optional[float] = None
    x1_norm: Optional[float] = None
    y1_norm: Optional[float] = None

    def update(
            self,
            x0: Optional[float],
            y0: Optional[float],
            x1: Optional[float],
            y1: Optional[float]
        ) -> None:
        """Update the bounding box coordinates to encompass the given coordinates.

        Adjusts the current bounding box by expanding its boundaries to
        include the specified coordinates (x0, y0, x1, y1). If a new
        coordinate is provided, the minimum and maximum values are
        recalculated to ensure the bounding box covers the new area.

        Parameters
        ----------
        x0 : float, optional
            The x-coordinate of the top-left corner.
        y0 : float, optional
            The y-coordinate of the top-left corner.
        x1 : float, optional
            The x-coordinate of the bottom-right corner.
        y1 : float, optional
            The y-coordinate of the bottom-right corner.
        """
        self.x0 = min(self.x0, x0) if x0 else self.x0
        self.y0 = min(self.y0, y0) if y0 else self.y0
        self.x1 = max(self.x1, x1) if x1 else self.x1
        self.y1 = max(self.y1, y1) if y1 else self.y1

    def normalize(
            self,
            width: float,
            height: float
        ) -> None:
        """Normalize the bounding box coordinates based on the given width and height.

        Parameters
        ----------
        width : float
            The width to normalize the x-coordinates.
        height : float
            The height to normalize the y-coordinates.

        Raises
        ------
        ZeroDivisionError
            If `width` or `height` is zero.
        """
        self.x0_norm, self.y0_norm, self.x1_norm, self.y1_norm = (
            self.x0 / width,
            self.y0 / height,
            self.x1 / width,
            self.y1 / height
        )

class TextBlock:
    """Represents a block of text with associated metadata and methods
    for serialization and representation.

    Parameters
    ----------
    id : str
        Unique identifier for the text block.
    content : str
        The original text content.
    coordinates : Optional[List[Union[int, float]]], optional
        A list representing the coordinates of the bounding box of the
        text within the original document, in the format `x0, y0, x1, y1`.

    Attributes
    ----------
    id : str
        Unique identifier for the text chunk.
    raw_content : str
        The original text content.
    processed_content : str
        Processed version of the text content.
    summarized_content : str
        Summarized version of the text content.
    embedding : List[float]
        List representing the embedding of the text content.
    coordinates : List[int | float]
        Coordinates of the text block's bounding box in the document.

    Methods
    -------
    `serialize_content(raw=False, processed=False, embedding=False)` -> Dict[str, Any]
        Retrieve specified content from the TextBlock instance.
    """
    processed_content: str = ""
    summarized_content: str = ""
    embedding: List[float] = []

    def __init__(
            self,
            id: str,
            content: str,
            coordinates: Optional[BoundingBox] = None
        ) -> None:
        self.id = id
        self.raw_content = content
        self.coord = coordinates

    def serialize_content(
            self,
            raw: bool = False,
            processed: bool = False,
            summarized: bool = False,
            embedding: bool = False
        ) -> Dict[str, Any]:
        """Retrieve specified content from the TextBlock instance.

        Parameters
        ----------
        raw : bool, optional
            If True, include raw content in the output. By default False.
        processed : bool, optional
            If True, include processed content in the output. By default
            False.
        summarized : bool, optional
            If True, include summarized content in the output. By
            default False.
        embedding : bool, optional
            If True, include the embedding of the content in the output.
            By default False.

        Returns
        -------
        Dict[str, Any]
            A dictionary containing the requested content types
            with keys 'raw', 'processed', 'summarized', and 'embedding'.
            Each key maps to the corresponding content or None if not
            requested.
        """
        return {
            "raw": self.raw_content if raw else None,
            "processed": self.processed_content if processed else None,
            "summarized": self.summarized_content if summarized else None,
            "embedding": self.embedding if embedding else None
        }

    def __len__(self) -> int:
        return len(self.raw_content)

    def __str__(self):
        return self.raw_content

    def __repr__(self):
        attributes = [
            attr for attr in [
                "raw_content",
                "processed_content",
                "summarized_content",
                "embedding"
            ] if getattr(self, attr, None)
        ]

        formatted_attrs = " and ".join(
            [", ".join(attributes[:-1]), attributes[-1]] if len(attributes) > 1 else attributes
        ) or "none"

        return f"{self.__class__} at {hex(id(self))} with attributes {formatted_attrs} valued"

class Page:
    """Represents a page of a document and collects blocks of text
    within the specified boundaries.

    Parameters
    ----------
    number : int
        The page number.
    content : pymupdf.Page
        The page content, expected to have an `artbox` attribute and
        a `get_text` method.
    normalize : bool, optional
        If True, normalize the bounding box coordinates relative to
        the page dimensions. By default False.

    Attributes
    ----------
    number : int
        Page number in the document.
    source_page_object : pymupdf.Page
        Original page object from which content is extracted.
    chunks : list of TextBlock
        List of text blocks extracted from the page content within the
        defined boundaries.
    full_text : TextBlock
        Single text block representing the entire page content within
        specified boundaries.

    Methods
    -------
    extract_paragraphs(normalize_coordinates=False) -> List[TextBlock]
        Extracts paragraphs from the page content within calculated
        boundaries.
    extract_bounded_text(normalize_coordinates=False) -> TextBlock
        Extracts text content and its bounding box from the page within
        specified boundaries.
    calculate_boundaries(width, height) -> Tuple[float, float, float, float]
        Calculate the boundaries of the text area on the page.
    get_serialized_content(raw_chunks=False, processed_chunks=False, embedded_chunks=False, flatten=True, exclude_empty=False) -> Dict[str, Any]
        Retrieves serialized content from the page's text chunks based on
        specified chunk types.
    """
    def __init__(
            self,
            number: int,
            page_object: pymupdf.Page,
            normalize: bool = False
        ) -> None:
        self.number = number
        self.source_page_object = page_object
        self.chunks = self.extract_paragraphs(normalize)
        self.full_text = self.extract_bounded_text(normalize)

    @property
    def width(self) -> float:
        """Width of the page's artbox."""
        if not hasattr(self, "_artbox_width"):
            if (hasattr(self.source_page_object, 'artbox') and
                hasattr(self.source_page_object.artbox, 'bottom_right')):
                self._artbox_width = self.source_page_object.artbox.bottom_right[0]
            else:
                raise AttributeError(
                    "`source_page_object` or its attributes are not properly initialized.")
        return self._artbox_width

    @property
    def height(self) -> float:
        """Height of the page's artbox."""
        if not hasattr(self, "_artbox_height"):
            if (hasattr(self.source_page_object, 'artbox') and
                hasattr(self.source_page_object.artbox, 'bottom_right')):
                self._artbox_height = self.source_page_object.artbox.bottom_right[1]
            else:
                raise AttributeError(
                    "`source_page_object` or its attributes are not properly initialized.")
        return self._artbox_height

    def extract_paragraphs(
            self,
            normalize_coordinates: bool = False
        ) -> List[TextBlock]:
        """Extracts paragraphs from the page content within calculated
        boundaries.

        Parameters
        ----------
        normalize_coordinates : bool, optional
            If True, normalize the bounding box coordinates relative to
            the page dimensions. By default False.

        Returns
        -------
        list of TextBlock
            A list of non-empty text blocks extracted from the page
            content.
        """
        boundaries = self.calculate_boundaries(self.width, self.height)
        content_text = self.source_page_object.get_textpage(clip=boundaries)
        page_content: List[
            Tuple[
                Union[int, float],
                Union[int, float],
                Union[int, float],
                Union[int, float],
                str,
                int,
                Literal[0, 1]
            ]
        ] = self.source_page_object.get_text( # type: ignore
            option="blocks", textpage=content_text)

        blocks: List[TextBlock] = []
        bbox = BoundingBox(
            float('inf'), float('inf'), -float('inf'), -float('inf'))
        for block in page_content:
            x0, y0, x1, y1, text, block_i, block_type = block

            if text.strip():  # Ignore empty blocks

                bbox.update(x0, y0, x1, y1)
                if normalize_coordinates:
                    # Normalize the bounding box coordinates
                    bbox.normalize(width=self.width, height=self.height)

                blocks.append(TextBlock(
                    id=f"{self.number}_{block_i}",
                    content=text,
                    coordinates=bbox
                ))
        return blocks

    def extract_bounded_text(
            self,
            normalize_coordinates: bool = False
        ) -> TextBlock:
        """Extracts text content and its bounding box from the page within
        specified boundaries.

        Parameters
        ----------
        normalize_coordinates : bool, optional
            If True, normalize the bounding box coordinates relative to
            the page dimensions. By default False.

        Returns
        -------
        TextBlock
            A TextBlock instance containing the concatenated extracted
            text and the smallest bounding box enclosing all extracted
            text blocks. If no text is extracted, the bounding box is
            None.

        Notes
        -----
        The extracted text is fully or partially inside the calculated
        boundaries.
        """
        # Compute the clipping boundaries
        x_min, y_min, x_max, y_max = self.calculate_boundaries(self.width, self.height)

        # Extract all text blocks from the page
        content_text = self.source_page_object.get_textpage()
        page_content = self.source_page_object.get_text(  # type: ignore
            option="blocks", textpage=content_text)

        # Sort text blocks for logical reading order (top-to-bottom, left-to-right)
        page_content = sorted(page_content, key=lambda b: (b[1], b[0]))

        extracted_texts: List[str] = []
        merged_bbox = BoundingBox(
            float('inf'), float('inf'), -float('inf'), -float('inf'))
        for block in page_content:
            x0, y0, x1, y1, text, _, _ = block  # Extract block bounding box

            if text.strip():  # Ignore empty blocks
                # Check if the block is fully inside or intersects the rectangle
                if not (x1 < x_min or x0 > x_max or y1 < y_min or y0 > y_max):
                    extracted_texts.append(text)

                    # Update the overall bounding box
                    merged_bbox.update(x0, y0, x1, y1)

        if extracted_texts and normalize_coordinates:
            # Normalize the bounding box coordinates
            merged_bbox.normalize(width=self.width, height=self.height)

        return TextBlock(
            id=f"{self.number}_bounded",
            content="\n".join(extracted_texts).strip(),
            coordinates=merged_bbox if extracted_texts else None
        )

    @staticmethod
    def calculate_boundaries(
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
        return str(self.source_page_object)

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
            If True, keeps the `Document.Page.TextBlock` structure
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
            # Maintain the structure Document.Page.TextBlock
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
