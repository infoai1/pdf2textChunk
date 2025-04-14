# --- START OF FILE app.py ---
import streamlit as st
import pandas as pd
import time

# Import functions from our modules
from utils import ensure_nltk_data, get_tokenizer
from file_processor import extract_sentences_with_structure
# Corrected import: Remove chunk_by_chapter as it's no longer in chunker.py
from chunker import chunk_structured_sentences

# --- Constants ---
TARGET_TOKENS = 200
OVERLAP_SENTENCES = 2 # Use 2 sentences for ~10-15% overlap approx

# --- Run Setup ---
nltk_ready = ensure_nltk_data()
tokenizer = get_tokenizer()

# --- Streamlit App UI ---
st.title("PDF/DOCX Structured Chunker v14") # Incremented version
st.write("Upload PDF or DOCX. Attempts heading detection. Chunks text by token count.")

uploaded_file = st.file_uploader("1. Upload Book File", type=["pdf", "docx"], key="file_uploader_v14")

st.sidebar.header("Processing Options")

# Removed chunk_mode selection as only token chunking is available now
# chunk_mode = st.sidebar.radio(...)

include_page_numbers = st.sidebar.checkbox("Include Page/Para Marker in Output?", value=True, key='page_num_toggle_v14')

st.sidebar.markdown("---")
st.sidebar.markdown("**PDF Specific Options (ignored for DOCX):**")
start_skip = st.sidebar.number_input("Pages to Skip at START", min_value=0, value=0, step=1)
end_skip = st.sidebar.number_input("Pages to Skip at END", min_value=0, value=0, step=1)
start_page_offset = st.sidebar.number_input("Actual Page # of FIRST Processed Page", min_value=1, value=1, step=1)


# --- Main App Logic ---
if not tokenizer: st.error("Tokenizer could not be loaded.")
elif not nltk_ready: st.error("NLTK 'punkt' data could not be verified/downloaded.")
elif uploaded_file is not None:
    if st.button("Process File", key="chunk_button_v14"):
        file_content = uploaded_file.getvalue()
        file_name = uploaded_file.name
        is_pdf = file_name.lower().endswith(".pdf")

        # Update settings display
        settings_info = f"Chunk Mode: By ~{TARGET_TOKENS} Tokens | Include Loc#: {include_page_numbers}"
        if is_pdf:
            settings_info += f" | PDF Skip: {start_skip} start, {end_skip} end | PDF Offset: {start_page_offset}"
        st.info(settings_info)

        with st.spinner("Step 1: Reading file and extracting structure..."):
            start_time = time.time()
            sentences_data = extract_sentences_with_structure(
                file_name, file_content,
                start_skip=int(start_skip) if is_pdf else 0,
                end_skip=int(end_skip) if is_pdf else 0,
                start_page_offset=int(start_page_offset) if is_pdf else 1
            )
            extract_time = time.time() - start_time
            st.write(f"Extraction took: {extract_time:.2f} seconds")

        if sentences_data is None: st.error("Failed to extract data.")
        elif not sentences_data: st.warning("No text content found.")
        else:
            st.success(f"Extracted {len(sentences_data)} items.")
            with st.spinner(f"Step 2: Chunking sentences into ~{TARGET_TOKENS} token chunks..."):
                start_time = time.time()
                # Always call the token-based chunker now
                chunk_list = chunk_structured_sentences(
                    sentences_data, tokenizer, TARGET_TOKENS, OVERLAP_SENTENCES
                )
                chunk_time = time.time() - start_time
                st.write(f"Chunking took: {chunk_time:.2f} seconds")

            if chunk_list:
                st.success(f"Processing complete. Generated {len(chunk_list)} chunks.")
                # Define columns based on chunk_structured_sentences output
                output_columns = ['chunk_text', 'page_number', 'chapter_title', 'subchapter_title']
                df = pd.DataFrame(chunk_list, columns=output_columns)

                # Ensure 'title' columns exist and fill NaNs
                df['chapter_title'] = df['chapter_title'].fillna("Unknown Chapter / Front Matter")
                df['subchapter_title'] = df['subchapter_title'].fillna("") # Subchapter might be None

                # Decide final columns based on user choice
                if include_page_numbers:
                     final_columns_for_csv = ['chunk_text', 'page_number', 'chapter_title', 'subchapter_title']
                     final_columns_for_display = final_columns_for_csv
                else:
                     final_columns_for_csv = ['chunk_text', 'chapter_title', 'subchapter_title']
                     final_columns_for_display = final_columns_for_csv

                # Select existing columns only
                df_final = df[[col for col in final_columns_for_csv if col in df.columns]]
                st.dataframe(df[[col for col in final_columns_for_display if col in df.columns]])

                csv_data = df_final.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV", data=csv_data,
                    file_name=f'{uploaded_file.name}_chunks_v14.csv',
                    mime='text/csv', key="download_csv_v14"
                )
            else: st.error("Chunking failed or resulted in no chunks.")

# --- END OF FILE app.py ---
