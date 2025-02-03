from abc import ABC, abstractmethod
import datetime
from typing import List
import chromadb
import redis
from redis.commands.search.field import (
    NumericField,
    TagField,
    TextField,
    VectorField,
)
from redis.commands.search.indexDefinition import IndexDefinition, IndexType

from config.chroma import PERSIST_DIRRECTORY
from config.redis import DISTANCE_METRIC, INDEX_NAME, INDEX_TYPE
from indexing.components import Document
from logger.setup import LoggerManager
from utils import format_index_with_padding


class BaseDBHandler(ABC):
    """Abstract base class for database handlers.

    This class provides a template for database handlers, requiring
    implementation of the `add_document` method.

    Attributes
    ----------
    _log_mgr : LoggerManager
        An instance of LoggerManager for logging purposes.
    """

    def __init__(self, logger_manager: LoggerManager) -> None:
        self._log_mgr = logger_manager

    @abstractmethod
    def add_document(self, doc: Document) -> None:
        """Add the document `doc` to the database."""
        raise NotImplementedError("An abstract method is being called")

class ChromaHandler(BaseDBHandler):

    def __init__(
            self,
            logger_manager: LoggerManager,
            persist_directory: str = PERSIST_DIRRECTORY
        ) -> None:
        super().__init__(logger_manager=logger_manager)

        self.persist_path = persist_directory
        self.client = chromadb.PersistentClient(path=self.persist_path)

        self.init_collection()

        self._log_mgr.log_message(
            (f"Successfully initialised the instance {self.__class__.__name__} "
             f"at path {self.persist_path}."),
            "DEBUG"
        )

    def init_collection(self):
        self.collection = self.client.get_or_create_collection(
            name="doc_atlas",
            metadata={
                "description": "Chroma Collection for DocAtlas",
                "created": str(datetime.datetime.now())
            })

    def get_current_ids(self) -> List[str]:
        current_ids = self.collection.get()['ids']
        if not current_ids:
            self._log_mgr.log_message("The collection is empty.", "DEBUG")
        return list({index.split('_')[0] for index in current_ids})

    def add_document(
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
        Exception
            If an error occurs while adding a chunk to the collection.
        """
        self._log_mgr.log_message(
            f"Started inserting the document `{doc.metadata.title}` into the DB.",
            "INFO"
        )
        for page in doc.pages:

            step = int(len(page) * 0.3)  # Log about every 30% of completion
            for chunk_i, chunk in enumerate(page.chunks):

                if not stricted or chunk.embedding:
                    chnk_id = format_index_with_padding(
                        chunk.number, len(str(len(page))))

                    try:
                        self.collection.add(
                            documents=chunk.raw_content,
                            ids=f"{doc.metadata.id}_{page.number}_{chnk_id}",
                            embeddings=chunk.embedding,
                            metadatas={
                                "fileId": doc.metadata.id,
                                "fileName": doc.metadata.title,
                                "source": doc.metadata.embed_link,
                                "page": page.number,
                                "chunk": chunk.number
                            }
                        )
                    except Exception as e:
                        self._log_mgr.log_message(
                            f"Error adding chunk {chunk.number} on page {page.number}: {str(e)}",
                            "ERROR"
                        )

                    if step != 0 and (chunk_i + 1) % step == 0:
                        progress = (chunk_i + 1) / len(page) * 100
                        self._log_mgr.log_message(
                            (f"First {chunk_i+1} chunks of page {page.number} "
                             f"added to DB [{progress:.0f}%]."),
                            "DEBUG"
                        )
            self._log_mgr.log_message(f"Page {page.number} completed.", "DEBUG")

        self._log_mgr.log_message(
            "Insertion of the current document completed successfully.", "INFO")

class RedisHandler:

    def __init__(
            self,
            host: str = "localhost",
            port_number: int = 6379,
            decode_responses: bool = True
        ) -> None:
        self.client = redis.Redis(
            host=host, port=port_number, decode_responses=decode_responses)

    def add_document(self, document: Document) -> None:
        pipeline_insert = self.client.pipeline()

        serialized_document = document.serialize(
            raw_content=True,
            processed_content=True,
            content_embedding=True,
            keep_structure=False,
            exclude_missing_embeddings=True
        )

        redis_key = f"doc:{document.metadata.id}"
        pipeline_insert.json().set(redis_key, "$", serialized_document)

        try:
            insert_res = pipeline_insert.execute()
            if insert_res:
                print(f"Document {document.metadata.id} was successfully added to the DB.")
            else:
                print(f"Document {document.metadata.id} could not be added to the DB.")
        except Exception as e:
            print(f"Error loading document {document.metadata.id} into the DB: {e}")

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