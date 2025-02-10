from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, Optional
import chromadb
from chromadb.config import Settings
import redis
from redis.commands.search.field import (
    NumericField,
    TagField,
    TextField,
    VectorField,
)
from redis.commands.search.indexDefinition import IndexDefinition, IndexType

from config.chroma import PERSIST_DIRRECTORY, ANONYMIZED_TELEMETRY
from config.redis import DISTANCE_METRIC, INDEX_NAME, INDEX_TYPE
from indexing.components import ContextualQA, Document
from logger.setup import LoggerHandler


logger = LoggerHandler().get_logger(__name__)

class BaseDBHandler(ABC):
    """Abstract base class for database handlers.

    This class provides a template for database handlers, requiring
    implementation of the `add_embedding_entry` method.
    """

    @abstractmethod
    def add_entry(self, *args, **kwargs) -> None:
        """Add a new entry to the database."""
        raise NotImplementedError("An abstract method is being called")

class ChromaHandler(BaseDBHandler):
    """Handler for managing Chroma database collections.

    Attributes
    ----------
    persist_path : str
        The directory path where the database is persisted.
    client : chromadb.PersistentClient
        The client used to interact with the Chroma database.
    name : str
        The name of the collection being managed.
    collection : chromadb.Collection
        The collection object for the specified name.

    Methods
    -------
    `get_current_ids()` -> List[str]
        Retrieve the current unique IDs from the collection.
    """

    def __init__(
            self,
            collection_name: Literal["documents", "contextual_questions_answers"],
            collection_metadata: Optional[Dict[str, Any]],
            persist_directory: str
        ) -> None:
        self.persist_path = persist_directory
        self.client = chromadb.PersistentClient(
            path=self.persist_path,
            settings=Settings(anonymized_telemetry=ANONYMIZED_TELEMETRY)
        )

        if (not isinstance(collection_name, str) or
            collection_name.lower() not in ("documents", "contextual_questions_answers")):
            logger.error(
                "The name of the collection may be one of (\"documents\", "
                f"\"contextual_questions_answers\"). Instead, {collection_name} is provided."
            )
            raise ValueError("Collection name not recognised")

        self.name = collection_name
        self.collection = self.client.get_or_create_collection(
            name=self.name,
            metadata=collection_metadata
        )

        logger.debug(
            (f"Successfully initialised the instance {self.__class__.__name__} "
             f"with the collection {self.name} at path {self.persist_path}."))

    def get_current_ids(self) -> List[str]:
        """Retrieve the current unique IDs from the collection."""
        current_ids = self.collection.get()['ids']
        if not current_ids:
            logger.debug("The collection is empty.")
        return list({index.split('_')[0] for index in current_ids})

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
            "documents",
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

class CQACollectionHandler(ChromaHandler):

    def __init__(
            self,
            metadata: Optional[Dict[str, Any]] = None,
            persist_directory: str = PERSIST_DIRRECTORY
        ) -> None:
        super().__init__(
            "contextual_questions_answers",
            collection_metadata=metadata,
            persist_directory=persist_directory
        )

    def add_entry(
            self,
            cqa: ContextualQA
        ) -> None:
        if self.name != "contextual_questions_answers":
            logger.error(
                ("Wrong collection to add a context-questions-answers "
                 "completion. The correct one is \"contextual_questions_answers\".")
            )
            raise ValueError("Wrong collection")
        if not isinstance(cqa, ContextualQA):
            raise TypeError(
                f"`cqa` must be a ContextualizedQuestions instance, not a {type(cqa)}")

        logger.info(f"Inputting current questions and answers into the DB.")

        cqa_ids = [f"{cqa.id}_{i}" for i in range(3)]
        try:
            self.collection.add(
                documents=batch_documents,
                ids=cqa_ids,
                metadatas=batch_metadatas
            )
        except Exception as e:
            logger.error(f"Error adding chunks of page {page.number}: {e}")

class RedisHandler(BaseDBHandler):

    def __init__(
            self,
            collection_name: Literal["documents", "contextual_questions_answers"],
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