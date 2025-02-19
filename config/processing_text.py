from typing import Any, Dict, Optional


# Management of procedures to be applied on the original text.
# The order in which they are presented is the orinde in which they are
# executed in the pipeline.
# ! Hint: the order in which the operations are presented has been
# tested to the hilt, it is advisable not to change the order but only
# the value.
STEPS: Dict[str, Dict[str, bool]] = dict(
    fastForward = {
        "cleanUpText": True,                # Conversion to lower case and removal of special characters.
    },
    inDepth = {
        "urlEmailRemoval": False,           # Removal of links and emails from the text. 
        "htmlTagRemoval": False,            # If you want to delete HTML tags that the text might contain.
        "contractionExpansion": False,      # Convert contractions for better tokenization.
        "digitsRemoval": False,             # If the numbers are not significant, exclude them from the text.
        "handlingSpellingErrors": False,    # Correction of spelling errors in the text.
        "synonymReplacement": False,        # Replace words with common synonyms.
        "smartLowercasing": False,          # Lower case but preserving proper names.
        "entityMasking": False,             # Removal of entities for anonymisation of sensitive data.
        "stopWordsRemoval": False,          # Removal of stopwords and lemmatisation of tokens.
        "wordLemmatization": False,         # Converting words into lemmas.
        "extraWhitespacesRemoval": False,   # Removal of unnecessary extra spaces.
        "cleanUpText": False,               # Conversion to lower case and removal of special characters.
    }
)

# The minimum length a text chunk must have in order not to be excluded
# during the processing phase.
MIN_CHUNK_LENGTH: Optional[int] = 200

# To genereare a summary of the content of the pages.
SUMMARIZATION: Dict[str, Any] = dict(
    active = True,
    modelName = "facebook/bart-large-cnn",  # Summarization model.
    maxSummaryLength = 150,                 # The maximum length that tokens generated for the summary may have.
    minSummaryLength = 50                   # The minimum length that tokens generated for the summary may have.
)

# Should one or more of the modules required for the correct functioning
# of NLTK be missing, download it. Otherwise, skip the processing
# operations where those modules are required.
INSTALL_MISSING_NLTK: bool = True