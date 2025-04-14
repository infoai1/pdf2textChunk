# --- START OF FILE utils.py ---
import streamlit as st
import nltk
import tiktoken

@st.cache_resource
def ensure_nltk_data():
    """Checks for and downloads NLTK data if missing."""
    data_ok = True
    resources = {'punkt': 'tokenizers/punkt'} # Only punkt needed usually
    for name, path in resources.items():
        try:
            nltk.data.find(path)
        except LookupError:
            st.sidebar.info(f"Downloading NLTK data package: '{name}'...")
            try:
                nltk.download(name, quiet=True)
                st.sidebar.success(f"NLTK data '{name}' downloaded.")
            except Exception as e:
                st.sidebar.error(f"Download Error: Failed for NLTK '{name}'. Error: {e}")
                data_ok = False
        except Exception as e_find:
            st.sidebar.error(f"NLTK Find Error ({name}): {e_find}")
            data_ok = False
    if not data_ok:
        st.error("Essential NLTK data ('punkt') could not be verified/downloaded.")
    return data_ok

@st.cache_resource
def get_tokenizer():
    """Initializes and returns the tokenizer."""
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        st.error(f"Error initializing tokenizer: {e}")
        return None
# --- END OF FILE utils.py ---
