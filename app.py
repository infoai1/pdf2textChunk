import streamlit as st
import pandas as pd
import time
import re # Needed for keyword pattern validation

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
st.title("PDF/DOCX Configurable Chunker v15")
st.write("Upload PDF or DOCX. Define heading style, choose chunking method.")

uploaded_file = st.file_uploader("1. Upload Book File", type=["pdf", "docx"], key="file_uploader_v15")

# --- Sidebar Options ---
st.sidebar.header("Processing Options")

# Heading Style Selection
st.sidebar.subheader("Define Chapter Heading Style")
st.sidebar.caption("Select all criteria that apply to chapter titles in this document.")

# Style
use_style = st.sidebar.checkbox("Check Font Style?", value=True, key='use_style')
col1, col2 = st.sidebar.columns(2)
with col1:
    require_bold = st.checkbox("Must be Bold?", value=False, key='req_bold', disabled=not use_style)
with col2:
    require_italic = st.checkbox("Must be Italic?", value=True, key='req_italic', disabled=not use_style)

# Case
use_case = st.sidebar.checkbox("Check Text Case?", value=True, key='use_case')
col1a, col2a = st.sidebar.columns(2)
with col1a:
    require_title_case = st.checkbox("Must be Title Case?", value=True, key='req_title', disabled=not use_case)
with col2a:
    require_all_caps = st.checkbox("Must be ALL CAPS?", value=False, key='req_caps', disabled=not use_case)

if require_title_case and require_all_caps and use_case:
     st.sidebar.warning("Title Case and ALL CAPS selected - heading must match both.", icon="⚠️")

# Layout
use_layout = st.sidebar.checkbox("Check Layout?", value=True, key='use_layout')
col1b, col2b = st.sidebar.columns(2)
with col1b:
    require_centered = st.checkbox("Must be Centered (Approx)?", value=True, key='req_center', disabled=not use_layout)
with col2b:
    require_isolated = st.checkbox("Must be Alone in Block?", value=True, key='req_isolate', disabled=not use_layout, help="Checks if heading is the only line in its paragraph/block (PDF only).")

# Length
use_length = st.sidebar.checkbox("Check Word Count?", value=True, key='use_length')
col1c, col2c = st.sidebar.columns(2)
with col1c:
    min_words = st.number_input("Min Words", min_value=1, value=1, step=1, key='min_w', disabled=not use_length)
with col2c:
    max_words = st.number_input("Max Words", min_value=1, value=10, step=1, key='max_w', disabled=not use_length) # Default max 10

# Keywords
use_keywords = st.sidebar.checkbox("Check for Keywords/Pattern?", value=False, key='use_kw') # Default False
keyword_pattern = st.text_input("Regex Pattern (optional, case-insensitive)", value="", key='kw_pattern', disabled=not use_keywords, help="e.g., `CHAPTER \\d+` or `Introduction|Conclusion`")

# --- Chunking Mode ---
st.sidebar.subheader("Chunking Method")
chunk_mode = st.sidebar.radio(
    "Select Chunking Mode:",
    ('Chunk by ~200 Tokens (with overlap)', 'Chunk by Detected Chapter Title'),
    key='chunk_mode_select_v15'
)
include_page_numbers = st.sidebar.checkbox("Include Page/Para Marker?", value=True, key='page_num_toggle_v15')

# --- PDF Specific Options ---
st.sidebar.markdown("---")
st.sidebar.markdown("**PDF Specific Options (ignored for DOCX):**")
start_skip = st.sidebar.number_input("Pages to Skip at START", min_value=0, value=0, step=1)
end_skip = st.sidebar.number_input("Pages to Skip at END", min_value=0, value=0, step=1)
start_page_offset = st.sidebar.number_input("Actual Page # of FIRST Processed Page", min_value=1, value=1, step=1)


# --- Main App Logic ---
if not tokenizer: st.error("Tokenizer failed to load.")
elif not nltk_ready: st.error("NLTK 'punkt' data could not be verified/downloaded.")
elif uploaded_file is not None:
    if st.button("Process File", key="chunk_button_v15"):

        # --- Compile Heading Criteria from UI selections ---
        heading_criteria = {
            "use_style": use_style, # Pass the master toggle too if needed by heuristic
            "require_bold": require_bold,
            "require_italic": require_italic,
            "use_case": use_case,
            "require_title_case": require_title_case,
            "require_all_caps": require_all_caps,
            "use_layout": use_layout,
            "require_centered": require_centered,
            "require_isolated": require_isolated,
            "use_length": use_length,
            "min_words": min_words,
            "max_words": max_words,
            "use_keywords": use_keywords,
            "keyword_pattern": keyword_pattern.strip() if use_keywords and keyword_pattern.strip() else None
        }

        # --- Validation for Custom Regex (IF using that style option) ---
        # If you re-introduce the 'Custom Regex' option in the UI selectbox,
        # add the validation back here using heading_criteria['keyword_pattern']
        if heading_criteria["keyword_pattern"]:
             try: re.compile(heading_criteria["keyword_pattern"], re.IGNORECASE)
             except re.error as e:
                  st.error(f"Invalid Regex in Keyword Pattern: {e}")
                  st.stop() # Stop processing

        # --- Get File Info ---
        file_content = uploaded_file.getvalue()
        file_name = uploaded_file.name
        is_pdf = file_name.lower().endswith(".pdf")

        # Display Settings
        # Build a summary of active criteria for the info box
        active_criteria_summary = []
        if heading_criteria['use_style']: active_criteria_summary.append(f"Style(B:{heading_criteria['require_bold']},I:{heading_criteria['require_italic']})")
        if heading_criteria['use_case']: active_criteria_summary.append(f"Case(T:{heading_criteria['require_title_case']},A:{heading_criteria['require_all_caps']})")
        if heading_criteria['use_layout']: active_criteria_summary.append(f"Layout(C:{heading_criteria['require_centered']},I:{heading_criteria['require_isolated']})")
        if heading_criteria['use_length']: active_criteria_summary.append(f"Len({heading_criteria['min_words']}-{heading_criteria['max_words']})")
        if heading_criteria['keyword_pattern']: active_criteria_summary.append("Keyword")

        settings_info = f"Chunk Mode: '{chunk_mode}' | Include Loc#: {include_page_numbers} | Heading Criteria: {', '.join(active_criteria_summary) if active_criteria_summary else 'None Active'}"
        if is_pdf:
            settings_info += f" | PDF Skip: {start_skip} start, {end_skip} end | PDF Offset: {start_page_offset}"
        st.info(settings_info)


        with st.spinner("Step 1: Reading file and extracting structure..."):
            start_time = time.time()
            # Pass the dictionary of heading criteria
            sentences_data = extract_sentences_with_structure(
                file_name=file_name,
                file_content=file_content,
                heading_criteria=heading_criteria, # Pass the whole dictionary
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
            # --- Conditional Chunking ---
            if chunk_mode == 'Chunk by Detected Chapter Title':
                with st.spinner("Step 2: Chunking by chapter title..."):
                    start_time = time.time()
                    # Pass the 3-element tuples expected by chunk_by_chapter
                    # (Need to adjust output of extract_sentences if it changed)
                    # Assuming extract_sentences_with_structure returns (text, marker, chapter_title_or_None)
                    chunk_list = chunk_by_chapter(sentences_data)
                    chunk_time = time.time() - start_time
                    st.write(f"Chapter chunking took: {chunk_time:.2f} seconds")
                output_columns = ['title', 'chunk_text'] # Columns for this mode
            else: # Default to token-based chunking
                 with st.spinner(f"Step 2: Chunking into ~{TARGET_TOKENS} token chunks..."):
                    start_time = time.time()
                    # Pass the 3-element tuples expected by chunk_structured_sentences
                    chunk_list = chunk_structured_sentences(
                        sentences_data, tokenizer, TARGET_TOKENS, OVERLAP_SENTENCES
                    )
                    chunk_time = time.time() - start_time
                    st.write(f"Token chunking took: {chunk_time:.2f} seconds")
                 # Adjust expected columns based on chunk_structured_sentences output
                 output_columns = ['chunk_text', 'page_number', 'title'] # Assumes 'title' key is used

            # --- Process Results ---
            if chunk_list:
                st.success(f"Processing complete. Generated {len(chunk_list)} chunks.")
                # Dynamically determine columns based on the chosen mode's output
                df = pd.DataFrame(chunk_list) # Create DF from list of dicts

                # Standardize title column and fill NaNs
                if 'title' not in df.columns: df['title'] = "Unknown"
                df['title'] = df['title'].fillna("Unknown Chapter / Front Matter")

                # Decide final columns based on user choice and chunk mode
                final_columns = []
                if 'chunk_text' in df.columns: final_columns.append('chunk_text')
                if include_page_numbers and 'page_number' in df.columns:
                    final_columns.append('page_number')
                if 'title' in df.columns: final_columns.append('title')

                if not final_columns or 'chunk_text' not in final_columns :
                    st.error("Error processing columns for output.")
                else:
                    df_display = df[final_columns] # Select only desired columns
                    st.dataframe(df_display)
                    csv_data = df_display.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="Download data as CSV", data=csv_data,
                        file_name=f'{uploaded_file.name}_chunks_v15.csv',
                        mime='text/csv', key="download_csv_v15"
                    )
            else: st.error("Chunking resulted in no data.")

# --- END OF FILE app.py ---
