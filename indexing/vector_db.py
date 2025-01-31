import redis
from redis.commands.search.field import (
    NumericField,
    TagField,
    TextField,
    VectorField,
)
from redis.commands.search.indexDefinition import IndexDefinition, IndexType

from config.redis import DISTANCE_METRIC, INDEX_NAME, INDEX_TYPE
from indexing.components import Document


class RedisHandler:

    def __init__(
            self,
            host: str="localhost",
            port_number: int=6379,
            decode_responses: bool=True
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
            exclude_missing_embeddings=True)

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