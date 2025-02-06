from typing import Dict, Optional


# Management of procedures to be applied on the original text.
# The order in which they are presented is the orinde in which they are
# executed in the pipeline.
# ! Hint: the order in which the operations are presented has been
# tested to the hilt, it is advisable not to change the order but only
# the value.
STEPS: Dict[str, Dict[str, bool]] = dict(
    fastForward = {
        "cleanUpText": False,                # Conversion to lower case and removal of special characters.
        "stopWordsRemoval": False,           # Removal of stopwords and lemmatisation of tokens.
        "wordLemmatization": False           # Converting words into lemmas.
    },
    inDepth = {
        "urlEmailRemoval": True,            # Removal of links and emails from the text. 
        "htmlTagRemoval": True,             # If you want to delete HTML tags that the text might contain.
        "contractionExpansion": True,       # Convert contractions for better tokenization.
        "digitsRemoval": True,              # If the numbers are not significant, exclude them from the text.
        "handlingSpellingErrors": True,     # Correction of spelling errors in the text.
        "synonymReplacement": True,        # Replace words with common synonyms.
        "smartLowercasing": True,          # Lower case but preserving proper names.
        "entityMasking": True,             # Removal of entities for anonymisation of sensitive data.
        "stopWordsRemoval": True,           # Removal of stopwords and lemmatisation of tokens.
        "wordLemmatization": True,          # Converting words into lemmas.
        "extraWhitespacesRemoval": True,    # Removal of unnecessary extra spaces.
        "cleanUpText": True,                # Conversion to lower case and removal of special characters.
    }
)

# The minimum length a text chunk must have in order not to be excluded
# during the processing phase.
MIN_CHUNK_LENGTH: Optional[int] = 200

# Should one or more of the modules required for the correct functioning
# of NLTK be missing, download it. Otherwise, skip the processing
# operations where those modules are required.
INSTALL_MISSING_NLTK: bool = True