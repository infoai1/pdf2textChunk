import streamlit as st
import pandas as pd
import tiktoken
import time

# Import functions from our modules
# Make sure pdf_utils.py and chunker.py are in the same directory
from pdf_utils import extract_sentences_with_structure, download_nltk_data
from chunker import chunk_structured_sentences

# --- Constants ---
TARGET_TOKENS = 200
OVERLAP_SENTENCES = 2 # Number of sentences to overlap

# --- Ensure NLTK data is available ---
# Use sidebar for setup messages
st.sidebar.title("Setup Status")
punkt_ready = download_nltk_data('punkt', 'tokenizers/punkt')
punkt_tab_ready = download_nltk_data('punkt_tab', 'tokenizers/punkt_tab')

# --- Helper to get Tokenizer ---
@st.cache_resource # Cache the tokenizer loading
def get_tokenizer():
    """Initializes and returns the tokenizer."""
    try:
        # Using cl100k_base, common for GPT-3.5/4
        return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        st.error(f"Error initializing tokenizer: {e}")
        return None

# --- Streamlit App UI ---
st.title("PDF Structured Chunker v4")
st.write("""
Upload a PDF. This app attempts to:
1.  Clean metadata/footers.
2.  Detect Chapter & Subchapter headings (heuristically).
3.  Create overlapping sentence-based chunks (~{TARGET_TOKENS} tokens).
4.  Assign Chapter/Subchapter titles to chunks.
5.  Prevents chunks from crossing detected Chapter boundaries.
*Note: Heading detection requires tuning based on the PDF's specific format.*
""")

uploaded_file = st.file_uploader("Upload Book PDF", type="pdf", key="pdf_uploader_v4")

# Get tokenizer instance
tokenizer = get_tokenizer()

if not tokenizer:
    st.error("Tokenizer could not be loaded. Cannot proceed.")
elif not (punkt_ready and punkt_tab_ready):
    st.error("Essential NLTK data packages ('punkt', 'punkt_tab') could not be verified/downloaded. Cannot proceed.")
elif uploaded_file:
    if st.button("Process PDF", key="chunk_button_v4"):
        # Read file content only once
        pdf_content = uploaded_file.getvalue()

        with st.spinner("Step 1: Reading PDF, cleaning, and extracting structured sentences..."):
            start_time = time.time()
            sentences_data = extract_sentences_with_structure(pdf_content)
            extract_time = time.time() - start_time
            st.write(f"Extraction took: {extract_time:.2f} seconds")

        if sentences_data is None:
            st.error("Failed to extract data from PDF. Check if it's a valid, text-based PDF.")
        elif not sentences_data:
             st.warning("No text content could be extracted after cleaning.")
        else:
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
                # Define columns explicitly for clarity and desired order
                df = pd.DataFrame(chunk_list, columns=['chunk_text', 'page_number', 'chapter_title', 'subchapter_title'])

                # Fill forward NaN/None chapter titles to apply to subsequent chunks
                # Forward fill chapter title, reset subchapter when chapter changes (implicit in logic already)
                df['chapter_title'] = df['chapter_title'].ffill()
                 # Optional: Fill subchapter forward *until* the next subchapter or chapter occurs. Requires more complex logic.
                 # Basic forward fill for subchapter might be misleading if it spans too far.
                 # df['subchapter_title'] = df['subchapter_title'].ffill() # Use with caution

                # Handle potential NaN values in title columns for display/CSV
                df['chapter_title'] = df['chapter_title'].fillna("Unknown Chapter")
                df['subchapter_title'] = df['subchapter_title'].fillna("") # Fill NaN subchapters with empty string


                st.dataframe(df)

                csv_data = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV",
                    data=csv_data,
                    file_name=f'{uploaded_file.name.replace(".pdf", "")}_structured_chunks_v4.csv',
                    mime='text/csv',
                    key="download_csv_v4"
                )
            else:
                st.error("Chunking failed or resulted in no chunks.")
