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
st.sidebar.title("Setup Status")
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
st.title("PDF Structured Chunker v5 (with Page Skips & Font Analysis)")
st.write("Upload a PDF, specify pages to skip and the starting page number, then process.")

uploaded_file = st.file_uploader("1. Upload Book PDF", type="pdf", key="pdf_uploader_v5")

st.sidebar.header("Processing Options")
start_skip = st.sidebar.number_input("Pages to Skip at START", min_value=0, value=3, step=1, help="Number of initial pages (like cover, copyright) to ignore.")
end_skip = st.sidebar.number_input("Pages to Skip at END", min_value=0, value=3, step=1, help="Number of final pages (like index, ads) to ignore.")
start_page_offset = st.sidebar.number_input("Actual Page # of FIRST Processed Page", min_value=1, value=1, step=1, help="What is the real page number printed on the first page AFTER skipping the initial ones?")

# Get tokenizer instance
tokenizer = get_tokenizer()

if not tokenizer:
    st.error("Tokenizer could not be loaded. Cannot proceed.")
elif not (punkt_ready and punkt_tab_ready):
     st.error("Essential NLTK data packages ('punkt', 'punkt_tab') could not be verified/downloaded. Cannot proceed.")
elif uploaded_file:
    if st.button("Process PDF", key="chunk_button_v5"):
        pdf_content = uploaded_file.getvalue()

        st.info(f"Settings: Skip first {start_skip}, Skip last {end_skip}, Start numbering from page {start_page_offset}")

        with st.spinner("Step 1: Reading PDF, cleaning, analyzing fonts, and extracting structured sentences..."):
            start_time = time.time()
            # Make sure parameters are passed correctly
            sentences_data = extract_sentences_with_structure(
                pdf_content,
                start_skip=int(start_skip), # Ensure integers
                end_skip=int(end_skip),
                start_page_offset=int(start_page_offset)
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

                # Chapter titles are now assigned during chunking based on state
                # Subchapter titles are also assigned based on state when chunk is finalized

                df['chapter_title'] = df['chapter_title'].fillna("Unknown Chapter / Front Matter") # Fill any remaining NaNs just in case
                df['subchapter_title'] = df['subchapter_title'].fillna("")

                df = df.reset_index(drop=True)
                st.dataframe(df)

                csv_data = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV",
                    data=csv_data,
                    file_name=f'{uploaded_file.name.replace(".pdf", "")}_structured_chunks_v5_font.csv',
                    mime='text/csv',
                    key="download_csv_v5_font"
                )
            else:
                st.error("Chunking failed or resulted in no chunks.")
