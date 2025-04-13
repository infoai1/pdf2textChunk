import streamlit as st
import pandas as pd
import tiktoken
import time

# Import functions from our modules
from pdf_utils import extract_sentences_with_structure, download_nltk_data
from chunker import chunk_structured_sentences

# --- Constants ---
TARGET_TOKENS = 200
OVERLAP_SENTENCES = 2 # Number of sentences for overlap estimate

# --- Ensure NLTK data is available ---
# Use sidebar for setup messages
# st.sidebar.title("Setup Status") # Use main area for status
if 'nltk_checked' not in st.session_state:
    st.session_state.nltk_checked = False
if not st.session_state.nltk_checked:
    with st.spinner("Checking NLTK data..."):
        punkt_ready = download_nltk_data('punkt', 'tokenizers/punkt')
        punkt_tab_ready = download_nltk_data('punkt_tab', 'tokenizers/punkt_tab')
        if punkt_ready and punkt_tab_ready:
            st.session_state.nltk_checked = True
        else:
             st.error("Failed to verify/download necessary NLTK data. App cannot proceed.")
             st.stop() # Stop if NLTK data is not ready

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
st.title("PDF Structured Chunker v5 (with Page Skips)")
st.write("Upload a PDF, specify pages to skip and the starting page number, then process.")

uploaded_file = st.file_uploader("1. Upload Book PDF", type="pdf", key="pdf_uploader_v5")

st.sidebar.header("Processing Options")
start_skip = st.sidebar.number_input("Pages to Skip at START", min_value=0, value=3, step=1, help="Number of initial pages (like cover, copyright) to ignore.")
end_skip = st.sidebar.number_input("Pages to Skip at END", min_value=0, value=3, step=1, help="Number of final pages (like index, ads) to ignore.")
start_page_offset = st.sidebar.number_input("Actual Page # of FIRST Processed Page", min_value=1, value=1, step=1, help="What is the real page number printed on the first page AFTER skipping the initial ones?")

# Get tokenizer instance
tokenizer = get_tokenizer()

if uploaded_file and tokenizer:
    if st.button("Process PDF", key="chunk_button_v5"):
        # Read file content only once
        pdf_content = uploaded_file.getvalue()

        st.info(f"Settings: Skip first {start_skip}, Skip last {end_skip}, Start numbering from page {start_page_offset}")

        with st.spinner("Step 1: Reading PDF, cleaning, and extracting structured sentences..."):
            start_time = time.time()
            sentences_data = extract_sentences_with_structure(
                pdf_content,
                start_skip=start_skip,
                end_skip=end_skip,
                start_page_offset=start_page_offset # Pass the offset
            )
            extract_time = time.time() - start_time
            st.write(f"Extraction took: {extract_time:.2f} seconds")

        if sentences_data is None:
            st.error("Failed to extract data from PDF. Check if it's a valid, text-based PDF or adjust skip pages.")
        elif not sentences_data:
             st.warning("No text content could be extracted after cleaning and skipping pages.")
        else:
            st.success(f"Extracted {len(sentences_data)} potential sentences/headings from the selected page range.")
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
                df = pd.DataFrame(chunk_list, columns=['chunk_text', 'page_number', 'chapter_title', 'subchapter_title'])

                # Forward fill chapter titles
                df['chapter_title'] = df['chapter_title'].ffill()
                df['chapter_title'] = df['chapter_title'].fillna("Unknown Chapter") # Handle cases where no chapter was ever detected

                # Optionally fill subchapters (use carefully)
                # df['subchapter_title'] = df['subchapter_title'].fillna("")

                # Reset index for cleaner display if needed
                df = df.reset_index(drop=True)

                st.dataframe(df)

                csv_data = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV",
                    data=csv_data,
                    file_name=f'{uploaded_file.name.replace(".pdf", "")}_structured_chunks_v5.csv',
                    mime='text/csv',
                    key="download_csv_v5"
                )
            else:
                st.error("Chunking failed or resulted in no chunks.")
elif not tokenizer:
     st.warning("Waiting for tokenizer...") # Updated message
elif not st.session_state.get('nltk_checked', False):
     st.warning("Waiting for NLTK check/download...") # Updated message
