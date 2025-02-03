# The minimum length a text chunk must have in order not to be excluded
# during the processing phase.
from typing import Optional


MIN_CHUNK_LENGTH: int = 100

# The fixed truncation length of the embedding. If None, the embedding
# size is left unchanged at the original size of the chosen model.
FIXED_EMBEDDING_LENGTH: Optional[int] = None

# The identifier of the pre-trained sentence transformer model for
# producing sentence embeddings.
MODEL_SENTENCE_TRANSFORMER = 'all-MiniLM-L6-v2'