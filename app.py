import streamlit as st
import pandas as pd
import tiktoken
import time

# Import functions from our modules
from pdf_utils import extract_sentences_with_structure, download_nltk_data
from chunker import chunk_structured_sentences

# --- Constants ---
TARGET_TOKENS = 200
OVERLAP_SENTENCES = 1 # Approx 10% token overlap (adjust if needed)

# --- Ensure NLTK data is available ---
st.sidebar.title("Setup Status")
punkt_ready = download_nltk_data('punkt', 'tokenizers/punkt')
# punkt_tab not needed for basic sent_tokenize usually
# punkt_tab_ready = download_nltk_data('punkt_tab', 'tokenizers/punkt_tab')
nltk_ready = punkt_ready # Simplified check

# --- Helper to get Tokenizer ---
@st.cache_resource
def get_tokenizer():
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        st.error(f"Error initializing tokenizer: {e}")
        return None

# --- Streamlit App UI ---
st.title("PDF Simplified Layout Chunker v6")
st.write("Upload PDF, specify page skips/offset. Attempts heading detection based on centering, length and breaks.")

uploaded_file = st.file_uploader("1. Upload Book PDF", type="pdf", key="pdf_uploader_v6")

st.sidebar.header("Processing Options")
start_skip = st.sidebar.number_input("Pages to Skip at START", min_value=0, value=0, step=1, help="Number of initial pages to ignore.")
end_skip = st.sidebar.number_input("Pages to Skip at END", min_value=0, value=0, step=1, help="Number of final pages to ignore.")
start_page_offset = st.sidebar.number_input("Actual Page # of FIRST Processed Page", min_value=1, value=1, step=1, help="Book's page number for the first page after skipping.")

tokenizer = get_tokenizer()

if not tokenizer:
    st.error("Tokenizer could not be loaded.")
elif not nltk_ready:
     st.error("NLTK 'punkt' data package could not be verified/downloaded.")
elif uploaded_file:
    if st.button("Process PDF", key="chunk_button_v6"):
        pdf_content = uploaded_file.getvalue()
        st.info(f"Settings: Skip first {start_skip}, Skip last {end_skip}, Start numbering from page {start_page_offset}")

        with st.spinner("Step 1: Reading PDF and extracting structure..."):
            start_time = time.time()
            sentences_data = extract_sentences_with_structure(
                pdf_content,
                start_skip=int(start_skip),
                end_skip=int(end_skip),
                start_page_offset=int(start_page_offset)
            )
            extract_time = time.time() - start_time
            st.write(f"Extraction took: {extract_time:.2f} seconds")

        if sentences_data is None:
            st.error("Failed to extract data. Check PDF validity and skip settings.")
        elif not sentences_data:
             st.warning("No text content found after cleaning/skipping.")
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
                # Output columns based on simplified chunker output
                df = pd.DataFrame(chunk_list, columns=['chunk_text', 'page_number', 'chapter_title', 'subchapter_title'])
                # Chapter title is assigned based on last detected heading; ffill might not be needed if chunker state is correct
                df['chapter_title'] = df['chapter_title'].fillna("Unknown Chapter / Front Matter")
                df['subchapter_title'] = df['subchapter_title'].fillna("") # Ensure nulls are empty strings

                df = df.reset_index(drop=True)
                st.dataframe(df)

                csv_data = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV",
                    data=csv_data,
                    file_name=f'{uploaded_file.name.replace(".pdf", "")}_layout_chunks_v6.csv',
                    mime='text/csv',
                    key="download_csv_v6"
                )
            else:
                st.error("Chunking failed or resulted in no chunks.")
