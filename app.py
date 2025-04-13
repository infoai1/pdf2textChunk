import streamlit as st
import pandas as pd
import tiktoken
import time

# Import functions from our modules
from pdf_utils import extract_sentences_with_structure, download_nltk_data
from chunker import chunk_structured_sentences

# --- Constants (defined here for easy access in UI if needed later) ---
TARGET_TOKENS = 200
OVERLAP_SENTENCES = 2 # Number of sentences to overlap

# --- Ensure NLTK data is available ---
st.sidebar.title("NLTK Data Status")
punkt_ready = download_nltk_data('punkt', 'tokenizers/punkt')
punkt_tab_ready = download_nltk_data('punkt_tab', 'tokenizers/punkt_tab')

# --- Helper to get Tokenizer ---
@st.cache_resource # Cache the tokenizer loading
def get_tokenizer():
    """Initializes and returns the tokenizer."""
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        st.error(f"Error initializing tokenizer: {e}")
        return None

# --- Streamlit App UI ---
st.title("PDF Structured Chunker v3")
st.write("Upload a PDF to clean, detect structure (chapters/subchapters), and create overlapping sentence-based chunks.")

uploaded_file = st.file_uploader("Upload Book PDF", type="pdf", key="pdf_uploader_v3")

# Get tokenizer instance
tokenizer = get_tokenizer()

if uploaded_file and tokenizer and punkt_ready and punkt_tab_ready:
    if st.button("Process PDF", key="chunk_button_v3"):
        # Read file content only once
        pdf_content = uploaded_file.getvalue()

        with st.spinner("Step 1: Reading PDF, cleaning, and extracting structured sentences..."):
            start_time = time.time()
            sentences_data = extract_sentences_with_structure(pdf_content)
            extract_time = time.time() - start_time
            st.write(f"Extraction took: {extract_time:.2f} seconds")

        if sentences_data:
            st.success(f"Extracted {len(sentences_data)} potential sentences/headings.")
            with st.spinner(f"Step 2: Chunking sentences into ~{TARGET_TOKENS} token chunks..."):
                start_time = time.time()
                chunk_list = chunk_structured_sentences(
                    sentences_data,
                    tokenizer,
                    TARGET_TOKENS,
                    OVERLAP_SENTENCES
                )
                chunk_time = time.time() - start_time
                st.write(f"Chunking took: {chunk_time:.2f} seconds")


            if chunk_list:
                st.success(f"Text chunked into {len(chunk_list)} chunks.")
                # Define columns explicitly for clarity
                df = pd.DataFrame(chunk_list, columns=['chunk_text', 'page_number', 'chapter_title', 'subchapter_title'])
                st.dataframe(df)

                csv_data = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV",
                    data=csv_data,
                    file_name=f'{uploaded_file.name.replace(".pdf", "")}_structured_chunks_v3.csv',
                    mime='text/csv',
                    key="download_csv_v3"
                )
            else:
                st.error("Chunking failed or resulted in no chunks.")
        else:
            st.error("Could not extract structured sentences from PDF. Check logs for PDF processing errors.")
elif not tokenizer:
     st.error("Could not initialize tokenizer. App cannot proceed.")
elif not (punkt_ready and punkt_tab_ready):
     st.error("Could not download necessary NLTK data. Please check internet connection and restart.")
