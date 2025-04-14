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
if not tokenizer: st.error("Tokenizer failed to load.")
elif not nltk_ready: st.error("NLTK 'punkt' data could not be verified/downloaded.")
elif uploaded_file is not None:
    if st.button("Process File", key="chunk_button_v15"): # Use the correct button key if needed

        # --- Compile Heading Criteria ---
        # (Keep the section that creates the heading_criteria dictionary based on UI selections)
        heading_criteria = {
            "require_bold": use_style and require_bold,
            "require_italic": use_style and require_italic,
            "require_title_case": use_case and require_title_case,
            "require_all_caps": use_case and require_all_caps,
            "require_centered": use_layout and require_centered,
            "require_isolated": use_layout and require_isolated,
            "min_words": min_words if use_length else 1,
            "max_words": max_words if use_length else 50,
            "keyword_pattern": keyword_pattern.strip() if use_keywords and keyword_pattern.strip() else None
        }
        # --- Validation for Custom Regex ---
        # (Keep this validation)
        is_custom_regex_mode = (selected_heading_style == "Custom Regex (Advanced)")
        user_custom_regex = custom_regex if is_custom_regex_mode else None # Use None if not selected
        if is_custom_regex_mode and not user_custom_regex:
            st.error("Please enter a Custom Regex pattern if that option is selected.")
            st.stop() # Stop processing
        if user_custom_regex:
             try: re.compile(user_custom_regex, re.IGNORECASE)
             except re.error as e:
                  st.error(f"Invalid Regex in Keyword Pattern: {e}")
                  st.stop() # Stop processing

        # --- Get File Info ---
        file_content = uploaded_file.getvalue()
        file_name = uploaded_file.name
        is_pdf = file_name.lower().endswith(".pdf")

        # Display Settings
        settings_info = f"Heading Style Hint: '{selected_heading_style}' | Include Loc#: {include_page_numbers}"
        if is_pdf:
            settings_info += f" | PDF Skip: {start_skip} start, {end_skip} end | PDF Offset: {start_page_offset}"
        st.info(settings_info)


        with st.spinner("Step 1: Reading file and extracting structure..."):
            start_time = time.time()
            # --- CORRECTED FUNCTION CALL ---
            sentences_data = extract_sentences_with_structure(
                file_name=file_name,                      # Pass filename
                file_content=file_content,                # Pass file content
                heading_style_hint=selected_heading_style, # Pass the user's selection string
                custom_regex=user_custom_regex,           # Pass the custom regex (or None)
                start_skip=int(start_skip) if is_pdf else 0,
                end_skip=int(end_skip) if is_pdf else 0,
                start_page_offset=int(start_page_offset) if is_pdf else 1
            )
            # --- END CORRECTION ---
            extract_time = time.time() - start_time
            st.write(f"Extraction took: {extract_time:.2f} seconds")

        # ...(rest of the app logic remains the same)...
        if sentences_data is None: st.error("Failed to extract data.")
        elif not sentences_data: st.warning("No text content found.")
        else:
            st.success(f"Extracted {len(sentences_data)} items.")
            # --- Conditional Chunking ---
            if chunk_mode == 'Chunk by Detected Chapter Title':
                with st.spinner("Step 2: Chunking by chapter title..."):
                    start_time = time.time()
                    chunk_list = chunk_by_chapter(sentences_data)
                    chunk_time = time.time() - start_time
                    st.write(f"Chapter chunking took: {chunk_time:.2f} seconds")
                output_columns = ['title', 'chunk_text']
                df_display_columns = output_columns
            else: # Default to token-based chunking
                 with st.spinner(f"Step 2: Chunking into ~{TARGET_TOKENS} token chunks..."):
                    start_time = time.time()
                    chunk_list = chunk_structured_sentences(
                        sentences_data, tokenizer, TARGET_TOKENS, OVERLAP_SENTENCES
                    )
                    chunk_time = time.time() - start_time
                    st.write(f"Token chunking took: {chunk_time:.2f} seconds")
                 output_columns = ['chunk_text', 'page_number', 'title'] # Default columns
                 df_display_columns = output_columns

            # --- Process Results ---
            if chunk_list:
                st.success(f"Processing complete. Generated {len(chunk_list)} chunks.")
                df = pd.DataFrame(chunk_list)
                if 'title' not in df.columns: df['title'] = "Unknown"
                df['title'] = df['title'].fillna("Unknown Chapter / Front Matter")

                if include_page_numbers and 'page_number' in df.columns:
                     final_columns_for_csv = ['chunk_text', 'page_number', 'title']
                else:
                     final_columns_for_csv = ['chunk_text', 'title']

                final_columns_for_csv = [col for col in final_columns_for_csv if col in df.columns]
                final_columns_for_display = final_columns_for_csv

                if not final_columns_for_csv: st.error("Error processing columns.")
                else:
                    df_final = df[final_columns_for_csv]
                    st.dataframe(df_final)
                    csv_data = df_final.to_csv(index=False).encode('utf-8')
                    st.download_button( label="Download data as CSV", data=csv_data,
                        file_name=f'{uploaded_file.name}_chunks_v15.csv', mime='text/csv', key="download_csv_v15"
                    )
            else: st.error("Chunking resulted in no data.")

# --- END OF FILE app.py ---
