# --- START OF FILE app.py ---
import streamlit as st
import pandas as pd
import time

# Import functions from our modules
from utils import ensure_nltk_data, get_tokenizer
from file_processor import extract_sentences_with_structure # Changed import
from chunker import chunk_structured_sentences, chunk_by_chapter # Import new chunker

# --- Constants ---
TARGET_TOKENS = 200
OVERLAP_SENTENCES = 2 # Use 2 sentences for ~10-15% overlap approx

# --- Run Setup ---
nltk_ready = ensure_nltk_data()
tokenizer = get_tokenizer()

# --- Streamlit App UI ---
st.title("PDF/DOCX Structured Chunker v13")
st.write("Upload PDF or DOCX. Attempts simple heading detection. Choose chunking method.")

uploaded_file = st.file_uploader("1. Upload Book File", type=["pdf", "docx"], key="file_uploader_v13")

st.sidebar.header("Processing Options")

# Chunking Mode Selection
chunk_mode = st.sidebar.radio(
    "Select Chunking Mode:",
    ('Chunk by ~200 Tokens (with overlap)', 'Chunk by Detected Chapter Title'),
    key='chunk_mode_select'
)

# Page Number Option
include_page_numbers = st.sidebar.checkbox("Include Page/Para Number in Output?", value=True, key='page_num_toggle')

st.sidebar.markdown("---") # Separator
st.sidebar.markdown("**PDF Specific Options (ignored for DOCX):**")
start_skip = st.sidebar.number_input("Pages to Skip at START", min_value=0, value=0, step=1)
end_skip = st.sidebar.number_input("Pages to Skip at END", min_value=0, value=0, step=1)
start_page_offset = st.sidebar.number_input("Actual Page # of FIRST Processed Page", min_value=1, value=1, step=1)

# --- Main App Logic ---
if not tokenizer: st.error("Tokenizer could not be loaded.")
elif not nltk_ready: st.error("NLTK 'punkt' data package could not be verified/downloaded.")
elif uploaded_file is not None:
    if st.button("Process File", key="chunk_button_v13"):
        file_content = uploaded_file.getvalue()
        file_name = uploaded_file.name
        is_pdf = file_name.lower().endswith(".pdf")

        # Display Settings
        settings_info = f"Chunk Mode: '{chunk_mode}' | Include Loc#: {include_page_numbers}"
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
            st.success(f"Extracted {len(sentences_data)} items (sentences/headings).")

            # --- Conditional Chunking ---
            if chunk_mode == 'Chunk by Detected Chapter Title':
                with st.spinner("Step 2: Chunking by chapter title..."):
                    start_time = time.time()
                    chunk_list = chunk_by_chapter(sentences_data)
                    chunk_time = time.time() - start_time
                    st.write(f"Chapter chunking took: {chunk_time:.2f} seconds")
                output_columns = ['title', 'chunk_text'] # Columns for this mode
                df_display_columns = ['title', 'chunk_text']
            else: # Default to token-based chunking
                 with st.spinner(f"Step 2: Chunking into ~{TARGET_TOKENS} token chunks..."):
                    start_time = time.time()
                    chunk_list = chunk_structured_sentences(
                        sentences_data, tokenizer, TARGET_TOKENS, OVERLAP_SENTENCES
                    )
                    chunk_time = time.time() - start_time
                    st.write(f"Token chunking took: {chunk_time:.2f} seconds")
                 output_columns = ['chunk_text', 'page_number', 'title'] # Default columns
                 df_display_columns = output_columns # Display all default

            # --- Process Results ---
            if chunk_list:
                st.success(f"Processing complete. Generated {len(chunk_list)} chunks.")
                df = pd.DataFrame(chunk_list)

                # Ensure 'title' column exists and fill NaNs
                if 'title' not in df.columns: df['title'] = "Unknown" # Add if missing (e.g., only token chunking ran)
                df['title'] = df['title'].fillna("Unknown Chapter / Front Matter")

                # Decide final columns based on user choice
                if include_page_numbers and 'page_number' in df.columns:
                     final_columns_for_csv = ['chunk_text', 'page_number', 'title']
                     final_columns_for_display = final_columns_for_csv
                else:
                     final_columns_for_csv = ['chunk_text', 'title']
                     final_columns_for_display = final_columns_for_csv

                # Ensure columns exist before selecting
                final_columns_for_csv = [col for col in final_columns_for_csv if col in df.columns]
                final_columns_for_display = [col for col in final_columns_for_display if col in df.columns]

                if not final_columns_for_csv: # Check if something went wrong
                     st.error("Error processing columns for output.")
                else:
                    df_final = df[final_columns_for_csv]
                    st.dataframe(df_final)
                    csv_data = df_final.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download data as CSV", data=csv_data,
                        file_name=f'{uploaded_file.name}_chunks_v13.csv',
                        mime='text/csv', key="download_csv_v13"
                    )
            else: st.error("Chunking resulted in no data.")

# --- END OF FILE app.py ---
