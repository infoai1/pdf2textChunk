import streamlit as st
import pandas as pd
import tiktoken
import time

from pdf_utils import extract_sentences_with_structure, download_nltk_data
from chunker import chunk_structured_sentences

# --- Constants ---
TARGET_TOKENS = 200
OVERLAP_SENTENCES = 2 # Using 2 sentences for overlap (~10-15% approximation)

# --- NLTK Setup ---
st.sidebar.title("Setup Status")
punkt_ready = download_nltk_data('punkt', 'tokenizers/punkt')
# Removed punkt_tab check as it wasn't needed previously
nltk_ready = punkt_ready

# --- Tokenizer Setup ---
@st.cache_resource
def get_tokenizer():
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        st.error(f"Error initializing tokenizer: {e}")
        return None

# --- Streamlit App UI ---
st.title("PDF Simplified Layout Chunker v7")
st.write("Upload PDF, specify skips/offset. Attempts heading detection based *primarily* on layout cues (centered, short, isolated line).")

uploaded_file = st.file_uploader("1. Upload Book PDF", type="pdf", key="pdf_uploader_v7")

st.sidebar.header("Processing Options")
start_skip = st.sidebar.number_input("Pages to Skip at START", min_value=0, value=0, step=1, help="e.g., Cover, Title, Copyright pages.")
end_skip = st.sidebar.number_input("Pages to Skip at END", min_value=0, value=0, step=1, help="e.g., Index, Ads pages.")
start_page_offset = st.sidebar.number_input("Actual Page # of FIRST Processed Page", min_value=1, value=1, step=1, help="Page number printed on the first content page.")

tokenizer = get_tokenizer()

if not tokenizer:
    st.error("Tokenizer could not be loaded.")
elif not nltk_ready:
     st.error("NLTK 'punkt' data package could not be verified/downloaded.")
elif uploaded_file:
    if st.button("Process PDF", key="chunk_button_v7"):
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
            st.error("Failed to extract data. Check PDF or adjust skip settings.")
        elif not sentences_data:
             st.warning("No text content found after cleaning/skipping.")
        else:
            st.success(f"Extracted {len(sentences_data)} potential sentences/headings.")
            with st.spinner(f"Step 2: Chunking sentences into ~{TARGET_TOKENS} token chunks with {OVERLAP_SENTENCES} sentence overlap..."):
                start_time = time.time()
                chunk_list = chunk_structured_sentences(
                    sentences_data,
                    tokenizer,
                    TARGET_TOKENS,
                    OVERLAP_SENTENCES # Pass overlap value
                )
                chunk_time = time.time() - start_time
                st.write(f"Chunking took: {chunk_time:.2f} seconds")

            if chunk_list:
                st.success(f"Text chunked into {len(chunk_list)} chunks.")
                # Explicitly define columns, subchapter is now always None from simplified logic
                df = pd.DataFrame(chunk_list, columns=['chunk_text', 'page_number', 'chapter_title', 'subchapter_title'])
                df['chapter_title'] = df['chapter_title'].fillna("Unknown Chapter / Front Matter")
                df['subchapter_title'] = "" # Set to empty string as it's not detected

                df = df.reset_index(drop=True)
                st.dataframe(df[['chunk_text', 'page_number', 'chapter_title']]) # Display without subchapter

                csv_data = df[['chunk_text', 'page_number', 'chapter_title']].to_csv(index=False).encode('utf-8') # Export without subchapter
                st.download_button(
                    label="Download data as CSV",
                    data=csv_data,
                    file_name=f'{uploaded_file.name.replace(".pdf", "")}_layout_chunks_v7.csv',
                    mime='text/csv',
                    key="download_csv_v7"
                )
            else:
                st.error("Chunking failed or resulted in no chunks.")
