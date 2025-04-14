# --- START OF FILE app.py ---
import streamlit as st
import pandas as pd
import time

# Import functions from our modules
from utils import ensure_nltk_data, get_tokenizer
from file_processor import extract_sentences_with_structure # Changed import
from chunker import chunk_structured_sentences

# --- Constants ---
TARGET_TOKENS = 200
OVERLAP_SENTENCES = 2 # Using 2 sentences for ~10-15% overlap approx

# --- Run Setup ---
nltk_ready = ensure_nltk_data()
tokenizer = get_tokenizer()

# --- Streamlit App UI ---
st.title("PDF/DOCX Structured Chunker v12")
st.write("Upload PDF or DOCX, specify PDF page skips/offset. Attempts heading detection based on style, case, length.")

uploaded_file = st.file_uploader("1. Upload Book File", type=["pdf", "docx"], key="file_uploader_v12")

st.sidebar.header("Processing Options")
st.sidebar.markdown("**PDF Specific Options:**")
start_skip = st.sidebar.number_input("Pages to Skip at START (PDF only)", min_value=0, value=0, step=1)
end_skip = st.sidebar.number_input("Pages to Skip at END (PDF only)", min_value=0, value=0, step=1)
start_page_offset = st.sidebar.number_input("Actual Page # of FIRST Processed Page (PDF only)", min_value=1, value=1, step=1)

if not tokenizer: st.error("Tokenizer failed to load.")
elif not nltk_ready: st.error("NLTK 'punkt' data package could not be verified/downloaded.")
elif uploaded_file is not None:
    if st.button("Process File", key="chunk_button_v12"):
        file_content = uploaded_file.getvalue()
        file_name = uploaded_file.name

        # Adjust settings display based on file type
        is_pdf = file_name.lower().endswith(".pdf")
        if is_pdf:
            st.info(f"Settings: Skip first {start_skip}, Skip last {end_skip}, Start numbering from page {start_page_offset}")
            skip_start_actual = int(start_skip)
            skip_end_actual = int(end_skip)
            offset_actual = int(start_page_offset)
        else: # For DOCX, ignore PDF settings
            st.info("Processing DOCX file (page skip/offset settings ignored).")
            skip_start_actual = 0
            skip_end_actual = 0
            offset_actual = 1 # Not really used for DOCX page numbers

        with st.spinner("Step 1: Reading file and extracting structure..."):
            start_time = time.time()
            # Pass parameters to the processing function
            sentences_data = extract_sentences_with_structure(
                file_name, # Pass filename to check extension
                file_content,
                start_skip=skip_start_actual,
                end_skip=skip_end_actual,
                start_page_offset=offset_actual
            )
            extract_time = time.time() - start_time
            st.write(f"Extraction took: {extract_time:.2f} seconds")

        if sentences_data is None: st.error("Failed to extract data.")
        elif not sentences_data: st.warning("No text content found.")
        else:
            st.success(f"Extracted {len(sentences_data)} items.")
            with st.spinner(f"Step 2: Chunking into ~{TARGET_TOKENS} token chunks..."):
                start_time = time.time()
                chunk_list = chunk_structured_sentences(
                    sentences_data, tokenizer, TARGET_TOKENS, OVERLAP_SENTENCES
                )
                chunk_time = time.time() - start_time
                st.write(f"Chunking took: {chunk_time:.2f} seconds")

            if chunk_list:
                st.success(f"Chunked into {len(chunk_list)} chunks.")
                df = pd.DataFrame(chunk_list, columns=['chunk_text', 'page_number', 'chapter_title', 'subchapter_title'])
                df['chapter_title'] = df['chapter_title'].fillna("Unknown Chapter / Front Matter")
                df['subchapter_title'] = df['subchapter_title'].fillna("") # Ensure empty string
                df = df.reset_index(drop=True)
                st.dataframe(df[['chunk_text', 'page_number', 'chapter_title', 'subchapter_title']]) # Display all columns now

                csv_data = df.to_csv(index=False).encode('utf-8') # Export all columns
                st.download_button(
                    label="Download data as CSV", data=csv_data,
                    file_name=f'{uploaded_file.name}_chunks_v12.csv',
                    mime='text/csv', key="download_csv_v12"
                )
            else: st.error("Chunking failed.")

# --- END OF FILE app.py ---
