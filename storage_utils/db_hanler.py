from abc import ABC, abstractmethod
import enum
import os
from pathlib import Path
import time
from typing import Any, Dict, Iterator, List, Literal, Optional, Union
import chromadb
import chromadb.errors
from chromadb.api.types import IncludeEnum, WhereDocument
from chromadb.types import Where
from chromadb.config import Settings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction # type: ignore
from dotenv import load_dotenv
import redis
from redis.commands.search.field import (
    NumericField,
    TagField,
    TextField,
    VectorField,
)
from redis.commands.search.indexDefinition import IndexDefinition, IndexType

from config.chroma import PERSIST_DIRRECTORY, ANONYMIZED_TELEMETRY
from config.embedding import MODEL_SENTENCE_TRANSFORMER
from config.redis import DISTANCE_METRIC, INDEX_NAME, INDEX_TYPE
from indexing.components import ContextualQA, Document
from logger.setup import LoggerHandler


load_dotenv()
ENVIRONMENT = os.environ.get('ENV', "DEV")

class CollectionName(str, enum.Enum):
    documents = "documents"
    questions = "contextual_questions"
    answers = "generated_answers"

logger = LoggerHandler().get_logger(__name__)

class BaseDBHandler(ABC):
    """Abstract base class for database handlers.

    This class provides a template for database handlers, requiring
    implementation of the `add_embedding_entry` method.
    """
    @property
    @abstractmethod
    def content(self) -> Any:
        """Current content of the collection."""
        raise NotImplementedError("An abstract property is being called")

    @property
    @abstractmethod
    def size(self) -> Any:
        """Current size of the collection."""
        raise NotImplementedError("An abstract property is being called")

    @abstractmethod
    def add_entry(self, *args, **kwargs) -> None:
        """Add a new entry to the database."""
        raise NotImplementedError("An abstract method is being called")

    @abstractmethod
    def walk(self) -> Iterator[Any]:
        """Iterate over the collection in chunks, yielding results as specified."""
        raise NotImplementedError("An abstract method is being called")

    @abstractmethod
    def empty_collection(self):
        """Remove all entries from the collection."""
        raise NotImplementedError("An abstract method is being called")

class ChromaHandler(BaseDBHandler):
    """Handler class for managing collections in a Chroma database.

    Attributes
    ----------
    persist_path : str
        Directory path for database persistence.
    client : chromadb.PersistentClient
        Client used to interact with the Chroma database.
    name : str
        Name of the managed collection.
    collection : chromadb.Collection
        Collection object for the specified name.

    Methods
    -------
    `setup_db(environment: str)` -> None
        Configures the database client based on the environment.
    `empty_collection()` -> None
        Deletes the current collection from the database.
    `get_current_ids()` -> List[str]
        Retrieves unique IDs from the collection.
    `get_content_by_doc(doc_id: str, include: list)` -> chromadb.GetResult
        Retrieves content for a specific document ID.
    `walk(chunk_size: int, doc_id: Optional[str], filter_doc: Optional[WhereDocument], include: Optional[List[IncludeEnum]])`
        Iterates over the collection in chunks, yielding results.
    """

    _persist_path: Path
    _cached_content: Optional[chromadb.GetResult]
    _cached_size: Optional[int]
    CACHE_TIMEOUT: int = 200

    def __init__(
            self,
            collection_name: CollectionName,
            collection_metadata: Optional[Dict[str, Any]],
            persist_directory: Union[Path, str],
            embedder_function: Optional[SentenceTransformerEmbeddingFunction] = None
        ) -> None:
        self.persist_path = persist_directory
        self.setup_db(ENVIRONMENT)

        if not isinstance(collection_name, (CollectionName, str)) or (
            isinstance(collection_name, str) and collection_name.lower() not in CollectionName
        ) or (
            isinstance(collection_name, CollectionName) and collection_name not in CollectionName
        ):
            logger.error(
                "The name of the collection may be one of "
                f"{', '.join(name.value for name in CollectionName)}. "
                f"Instead, '{collection_name}' is provided."
            )
            raise ValueError("Collection name not recognised")

        self.name = collection_name.value if isinstance(collection_name, CollectionName) else collection_name
        self.collection = self.client.get_or_create_collection(
            name=self.name,
            metadata=collection_metadata,
            embedding_function=embedder_function
        )

        self._cached_content = None
        self._cached_size = None

        logger.debug(
            (f"Successfully initialised the instance {self.__class__.__name__} "
             f"with the collection {self.name} at path {self.persist_path}."))

    def setup_db(self, environment: str) -> None:
        """Set up the database client based on the specified environment.

        Parameters
        ----------
        environment : str
            The environment in which the database is being set up. 
            Must be one of 'dev', 'development', 'tst', 'test', 'prd', 
            'prod', or 'production'.

        Raises
        ------
        ValueError
            If the provided environment is not recognized.
        """
        if hasattr(self, "client"):
            logger.warning("The current instance already has an active client.")
            return

        valid_environments = {
            'dev', 'development', 'tst', 'test', 'prd', 'prod', 'production'}
        if environment.lower() not in valid_environments:
            logger.error(f"Invalid environment: {environment}. Expected one of {valid_environments}.")
            raise ValueError("Invalid environment provided")

        if environment.lower() in ('dev', 'development'):
            logger.debug(
                f"Instantiating the db at the persistent path '{self.persist_path}'.")
            self.client = self._create_dev_db_client()

    @property
    def persist_path(self) -> Path:
        """Path to the directory where to save the data."""
        return self._persist_path

    @persist_path.setter
    def persist_path(self, value: Union[Path, str]) -> None:
        self._persist_path = Path(value)

    @property
    def content(self) -> chromadb.GetResult:
        if not self._cached_content or self._is_collection_modified():
            try:
                self._cached_content = self.collection.get(include=[
                    IncludeEnum.embeddings,
                    IncludeEnum.metadatas,
                    IncludeEnum.documents
                ])
                self._last_fetch_time = time.time()
            except Exception as e:
                logger.error(
                    f"Failed to retrieve content for collection '{self.name}': {e}")
                raise
        return self._cached_content

    @property
    def size(self) -> int:
        if not self._cached_size or self._is_collection_modified():
            try:
                self._cached_size = self.collection.count()
                self._last_fetch_time = time.time()
            except Exception as e:
                logger.error(
                    f"Failed to retrieve '{self.name}' collection size: {e}")
                return 0
        return self._cached_size

    def empty_collection(self) -> None:
        """Delete the current collection from the Chroma database."""
        try:
            self.client.delete_collection(self.name)
            logger.warning(f"Deleted collection: '{self.name}'.")
        except Exception as e:
            logger.error(f"Failed to empty the collection: {e}")
            raise

    def get_current_ids(self) -> List[str]:
        """Retrieve the current unique IDs from the collection."""
        current_ids = self.content['ids']
        if not current_ids:
            logger.debug("The collection is empty.")
        return list({index.split('_')[0] for index in current_ids})

    def get_content_by_doc(
            self,
            doc_id: str,
            include: Optional[List[IncludeEnum]] = None
        ) -> chromadb.GetResult:
        """Retrieve content from the collection for a specific document ID.

        Parameters
        ----------
        doc_id : str
            The unique identifier of the document to retrieve.
        include : list of {"embeddings", "metadatas", "documents"} or None, optional
            A list specifying which parts of the document to include in
            the result. Valid options are "embeddings", "metadatas", and
            "documents".

        Returns
        -------
        chromadb.GetResult
            The content of the document specified by the `doc_id`,
            including the requested parts.

        Raises
        ------
        ValueError
            If the `doc_id` is invalid or if the `include` parameter
            contains invalid options.
        Exception
            If there is an error retrieving the content from the
            collection.
        """
        if not isinstance(doc_id, str) or not doc_id.strip():
            logger.error("`doc_id` must be a valid string.")
            raise ValueError("Invalid `doc_id` provided")

        valid_includes = {
            item.value for item in IncludeEnum
            if item.value not in ("uris", "data", "distances")
        }
        # invalid_includes = [
        #     item.value for item in include if item not in valid_includes
        # ] if include is not None else []
        invalid_includes = set(include or []) - valid_includes # type: ignore
        if invalid_includes:
            logger.error(
                f"Invalid `include` parameter provided: '{"', '".join(invalid_includes)}'.")
            raise ValueError("Invalid `include` parameter provided")

        included_info = include or [IncludeEnum.metadatas, IncludeEnum.documents]
        try:
            result = self.collection.get(
                where={"fileId": {"$eq": doc_id}},
                include=included_info
            )
            return result
        except Exception as e:
            logger.error(
                f"Failed to retrieve content from collection '{self.name}' "
                f"for the document {doc_id}: {e}"
            )
            raise

    def walk(
            self,
            chunk_size: int = 10,
            doc_id: Optional[str] = None,
            filter_doc: Optional[WhereDocument] = None,
            include: Optional[List[IncludeEnum]] = None
        ) -> Iterator[chromadb.GetResult]:
        """Iterate over the collection in chunks, yielding results as specified.

        Parameters
        ----------
        chunk_size : int, optional
            The number of documents to retrieve per iteration. Must be a
            positive integer, by default 10.
        doc_id : str or None, optional
            The document ID to filter results by. Must be a valid string
            if provided, by default None.
        filter_doc : WhereDocument or None, optional
            Additional filter criteria for the documents, by default
            None. E.g. `{$contains: {"text": "hello"}}`.
        include : list of IncludeEnum or None, optional
            Specifies which parts of the documents to include in the
            results. Can contain `"embeddings"`, `"metadatas"`,
            `"documents"`. Ids are always included. By default None.

        Yields
        ------
        Iterator[chromadb.GetResult]
            An iterator over the collection's documents, retrieved in
            chunks.

        Raises
        ------
        ValueError
            If `chunk_size` is not a positive integer, `doc_id` is
            invalid, or `include` contains invalid options.
        """
        if not chunk_size or not isinstance(chunk_size, int) or chunk_size < 1:
            logger.error("`chunk_size` must be a positive integer.")
            raise ValueError("Invalid `chunk_size` provided")

        if doc_id and (not isinstance(doc_id, str) or not doc_id.strip()):
            logger.error("`doc_id` must be a valid string.")
            raise ValueError("Invalid `doc_id` provided")

        valid_includes = {
            item.value for item in IncludeEnum
            if item not in (
                IncludeEnum.uris, IncludeEnum.data, IncludeEnum.distances)
        }
        invalid_includes = set(include or []) - valid_includes # type: ignore
        if invalid_includes:
            logger.error(
                f"Invalid `include` parameter provided: '{"', '".join(invalid_includes)}'.")
            raise ValueError("Invalid `include` parameter provided")

        logger.debug(
            f"Fetching data from the '{self.name}' collection in {chunk_size}-record chunks"
            + (f" with filter: doc_id={doc_id}." if doc_id else ".")
        )
        where_condition: Optional[Where] = {"fileId": {"$eq": doc_id}} if doc_id else None
        included_info = include or [IncludeEnum.metadatas, IncludeEnum.documents]
        step = max(1, int(self.size * 0.2))  # Log about every 20% of completion

        for current_offset in range(0, self.size, chunk_size):
            result = self.collection.get(
                where=where_condition,
                limit=chunk_size,
                offset=current_offset,
                where_document=filter_doc,
                include=included_info
            )
            if not result['ids']:
                logger.warning(
                    "No other content available with current filters.")
                break
            yield result

            # if step != 0 and (
            #     (current_offset + chunk_size) % step == 0 or
            #     (current_offset + chunk_size) >= self.size):
            if current_offset % step == 0 or (current_offset + chunk_size) >= self.size:
                progress = (current_offset + chunk_size) / self.size * 100
                logger.debug(
                    f"Seen {progress:.0f}% of the total content of the collection."
                )

    def _create_dev_db_client(self):
        """Create and return a PersistentClient for interacting with the
        Chroma database.

        Raises
        ------
        FileExistsError
            If the directory for persistence cannot be created.
        chromadb.errors.ChromaError or Exception
            If the PersistentClient cannot be instantiated.
        """
        try:
            self.persist_path.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create the folder at {self.persist_path}: {e}.")
            raise

        try:
            return chromadb.PersistentClient(
                path=str(self.persist_path),
                settings=Settings(anonymized_telemetry=ANONYMIZED_TELEMETRY)
            )
        except chromadb.errors.ChromaError as e:
            logger.error(f"Chroma error while instantiating PersistentClient: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to instantiate PersistentClient: {e}")
            raise

    def _is_collection_modified(self) -> bool:
        return time.time() - self._last_fetch_time > self.CACHE_TIMEOUT

class DocumentCollectionHandler(ChromaHandler):
    """Class to handle operations for a collection of documents in a Chroma database.

    This class extends the ChromaHandler to specifically manage a
    collection of documents, allowing for the addition of documents with
    their pages and chunks to the database.

    Attributes
    ----------
    metadata : Optional[Dict[str, Any]]
        Metadata associated with the document collection.
    persist_directory : str
        Directory path where the collection data is persisted.

    Methods
    -------
    `add_embedding_entry(doc: Document, stricted: bool = True)` -> None
        Adds a document to the Chroma collection, processing each page
        and chunk, with optional strict checking for embeddings.
    """

    def __init__(
            self,
            metadata: Optional[Dict[str, Any]] = None,
            persist_directory: str = PERSIST_DIRRECTORY
        ) -> None:
        super().__init__(
            CollectionName.documents,
            collection_metadata=metadata,
            persist_directory=persist_directory
        )

    def add_entry(
            self,
            doc: Document,
            stricted: bool = True
        ) -> None:
        """Add a document to the Chroma collection, processing each page
        and chunk.

        Parameters
        ----------
        doc : Document
            The document to be added, containing pages and chunks.
        stricted : bool, optional
            If True, only chunks with embeddings are added. Default is
            True.

        Raises
        ------
        TypeError
            If `doc` is not an instance of Document.
        Exception
            If an error occurs while adding a chunk to the collection.
        """
        if self.name != "documents":
            logger.error(
                "Wrong collection to add a document to. The correct one is \"documents\"."
            )
            raise ValueError("Wrong collection")

        if not isinstance(doc, Document):
            logger.error(
                (f"A document of the wrong type was provided: `{type(doc)}` "
                 "instead of `Document`.")
            )
            raise TypeError(
                f"`doc` must be a Document instance, not a {type(doc)}")

        logger.info(f"Inserting the `{doc.metadata.title}` document into the DB.")
        step = int(len(doc) * 0.3)  # Log about every 30% of completion
        for page_i, page in enumerate(doc.pages):

            batch_documents = []
            batch_ids = []
            batch_embeddings = []
            batch_metadatas = []
            for chunk in page.chunks:

                if not stricted or chunk.embedding:
                    batch_documents.append(chunk.raw_content)
                    batch_ids.append(f"{doc.metadata.id}_{chunk.id}")
                    batch_embeddings.append(chunk.embedding)
                    batch_metadatas.append({
                        "fileId": doc.metadata.id,
                        "fileName": doc.metadata.title,
                        "source": doc.metadata.embed_link,
                        "page": page.number,
                        "chunk": int(chunk.id.split("_")[-1])
                    })

            if not batch_embeddings:
                logger.warning(
                    (f"None of the chunks on the {page.number} page have valid "
                     "text; insertion skipped."))
                continue
            try:

                self.collection.add(
                    documents=batch_documents,
                    ids=batch_ids,
                    embeddings=batch_embeddings,
                    metadatas=batch_metadatas
                )
            except Exception as e:
                logger.error(f"Error adding chunks of page {page.number}: {e}")
                raise

            if step != 0 and (page_i + 1) % step == 0:
                progress = (page_i + 1) / len(doc) * 100
                logger.debug(f"First {page_i+1} pages added to DB [{progress:.0f}%].")

        logger.info("Insertion of the current document completed successfully.")

class CQCollectionHandler(ChromaHandler):

    QA_AMOUNT = 3

    def __init__(
            self,
            metadata: Optional[Dict[str, Any]] = None,
            persist_directory: str = PERSIST_DIRRECTORY
        ) -> None:
        sentence_transformer_ef = SentenceTransformerEmbeddingFunction(
            model_name=MODEL_SENTENCE_TRANSFORMER
        )
        super().__init__(
            CollectionName.questions,
            collection_metadata=metadata,
            persist_directory=persist_directory,
            embedder_function=sentence_transformer_ef
        )

    def add_entry(
            self,
            cqa: ContextualQA
        ) -> None:
        if self.name != "contextual_questions":
            logger.error(
                ("Wrong collection to add a context-questions-answers "
                 "completion. The correct one is \"contextual_questions\".")
            )
            raise ValueError("Wrong collection")

        if not isinstance(cqa, ContextualQA):
            raise TypeError(
                f"`cqa` must be a ContextualizedQuestions instance, not a {type(cqa)}")

        logger.info("Inputting current contextualized questions into the DB.")

        file_id = cqa.context_id.split("_")[0]
        cqa_ids = [f"{cqa.context_id}_{i}" for i in range(self.QA_AMOUNT)]
        cqa_metadata = [{
            "fileId":file_id,
            "chunkId":cqa.context_id,
            "completionId": cqa.completion_id
        }] * self.QA_AMOUNT
        try:
            self.collection.add(
                documents=cqa.questions,
                ids=cqa_ids,
                metadatas=cqa_metadata # type: ignore
            )
        except Exception as e:
            logger.error(
                f"Error adding contextualized questions for document {file_id}: {e}")
            raise

        logger.info("Insertion of generated questions successfully completed.")

class GACollectionHandler(ChromaHandler):

    QA_AMOUNT = 3

    def __init__(
            self,
            metadata: Optional[Dict[str, Any]] = None,
            persist_directory: str = PERSIST_DIRRECTORY
        ) -> None:
        sentence_transformer_ef = SentenceTransformerEmbeddingFunction(
            model_name=MODEL_SENTENCE_TRANSFORMER
        )
        super().__init__(
            CollectionName.answers,
            collection_metadata=metadata,
            persist_directory=persist_directory,
            embedder_function=sentence_transformer_ef
        )

    def add_entry(
            self,
            cqa: ContextualQA
        ) -> None:
        if self.name != "generated_answers":
            logger.error(
                ("Wrong collection to add a context-questions-answers "
                 "completion. The correct one is \"generated_answers\".")
            )
            raise ValueError("Wrong collection")

        if not isinstance(cqa, ContextualQA):
            raise TypeError(
                f"`cqa` must be a ContextualizedQuestions instance, not a {type(cqa)}")

        logger.info("Inserting answers for contextualised questions into the DB.")

        file_id = cqa.context_id.split("_")[0]
        cqa_ids = [f"{cqa.context_id}_{i}" for i in range(self.QA_AMOUNT)]
        cqa_metadata = [{
            "fileId":file_id,
            "chunkId":cqa.context_id,
            "completionId": cqa.completion_id
        }] * self.QA_AMOUNT
        try:
            self.collection.add(
                documents=cqa.answers,
                ids=cqa_ids,
                metadatas=cqa_metadata # type: ignore
            )
        except Exception as e:
            logger.error(
                f"Error adding the answers related to document {file_id}: {e}")
            raise

        logger.info("The addition of the generated answers successfully completed.")

class RedisHandler(BaseDBHandler):

    def __init__(
            self,
            collection_name: Literal["documents", "contextual_questions"],
            host: str = "localhost",
            port_number: int = 6379,
            decode_responses: bool = True
        ) -> None:
        self.client = redis.Redis(
            host=host, port=port_number, decode_responses=decode_responses)

    def add_entry(self, doc: Document) -> None:
        pipeline_insert = self.client.pipeline()

        serialized_document = doc.serialize(
            raw_content=True,
            processed_content=True,
            content_embedding=True,
            keep_structure=False,
            exclude_missing_embeddings=True
        )

        redis_key = f"doc:{doc.metadata.id}"
        pipeline_insert.json().set(redis_key, "$", serialized_document)

        try:
            insert_res = pipeline_insert.execute()
            if insert_res:
                print(f"Document {doc.metadata.id} was successfully added to the DB.")
            else:
                print(f"Document {doc.metadata.id} could not be added to the DB.")
        except Exception as e:
            print(f"Error loading document {doc.metadata.id} into the DB: {e}")

    def create_index(self, vector_dimension: int):
        schema = [
            TagField("$.id", as_name="id"),  # Unique identifier for each document
            TextField("$.name", as_name="name"),  # Document name
            TextField("$.location", as_name="location"),  # File path
            TextField("$.content.*.processed", as_name="processed_text"),  # Processed text (for full-text search)
            NumericField("$.content.*.page", as_name="page_number"),  # Page numver text
            VectorField(
                "$.content.*.embedding",
                INDEX_TYPE, 
                {
                    "TYPE": "FLOAT32",
                    "DIM": vector_dimension,
                    "DISTANCE_METRIC": DISTANCE_METRIC,
                },
                as_name="vector"
            )
        ]

        try:
            definition = IndexDefinition(prefix=["doc:"], index_type=IndexType.JSON)
            res = self.client.ft(INDEX_NAME).create_index(
                fields=schema,
                definition=definition
            )
            print(f"Index '{INDEX_NAME}' created successfully: {res}")
        except Exception as e:
            print(f"Index creation failed: {e}")