from typing import Literal


# The name of the Redis index
INDEX_NAME: str = "idx:docAtlas"

# The indexing method, which is either a flat index or a hierarchical
# navigable small world graph (HNSW)
INDEX_TYPE: Literal["FLAT", "HNSW"] = "HNSW"

# The distance function for the embeddings
DISTANCE_METRIC: str = "COSINE"