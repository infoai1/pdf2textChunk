# --- START OF FILE app.py ---
import streamlit as st
import pandas as pd
import time
import re # Needed for keyword pattern validation

# Import functions from our modules
from utils import ensure_nltk_data, get_tokenizer
from file_processor import extract_sentences_with_structure # Correct import
from chunker import chunk_structured_sentences, chunk_by_chapter # Correct import

# --- Constants ---
TARGET_TOKENS = 200
OVERLAP_SENTENCES = 2

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
# --- Define the master toggles FIRST ---
use_style = st.sidebar.checkbox("Check Font Style?", value=True, key='use_style')
use_case = st.sidebar.checkbox("Check Text Case?", value=True, key='use_case')
use_layout = st.sidebar.checkbox("Check Layout?", value=True, key='use_layout') # Defined BEFORE use
use_length = st.sidebar.checkbox("Check Word Count?", value=True, key='use_length')
use_keywords = st.sidebar.checkbox("Check for Keywords/Pattern?", value=False, key='use_kw') # Default False

st.sidebar.subheader("Define Chapter Heading Style")
st.sidebar.caption("Select criteria that apply to chapter titles.")

# Style (conditional on use_style)
col1, col2 = st.sidebar.columns(2)
with col1:
    require_bold = st.checkbox("Must be Bold?", value=False, key='req_bold', disabled=not use_style)
with col2:
    require_italic = st.checkbox("Must be Italic?", value=True, key='req_italic', disabled=not use_style)

# Case (conditional on use_case)
col1a, col2a = st.sidebar.columns(2)
with col1a:
    require_title_case = st.checkbox("Must be Title Case?", value=True, key='req_title', disabled=not use_case)
with col2a:
    require_all_caps = st.checkbox("Must be ALL CAPS?", value=False, key='req_caps', disabled=not use_case)

if require_title_case and require_all_caps and use_case:
     st.sidebar.warning("Title Case & ALL CAPS selected.", icon="⚠️")

# Layout (conditional on use_layout) - Ensure use_layout is defined above
col1b, col2b = st.sidebar.columns(2)
with col1b:
    require_centered = st.checkbox("Must be Centered (Approx)?", value=True, key='req_center', disabled=not use_layout)
with col2b:
    # --- THIS IS THE CORRECTED LINE (around original line 57) ---
    require_isolated = st.checkbox("Must be Alone in Block?", value=True, key='req_isolate', disabled=not use_layout, help="Checks if heading is the only line in its paragraph/block (PDF only).")

# Length (conditional on use_length)
col1c, col2c = st.sidebar.columns(2)
with col1c:
    min_words = st.number_input("Min Words", min_value=1, value=1, step=1, key='min_w', disabled=not use_length)
with col2c:
    max_words = st.number_input("Max Words", min_value=1, value=10, step=1, key='max_w', disabled=not use_length)

# Keywords (conditional on use_keywords)
keyword_pattern = st.text_input("Regex Pattern (optional, case-insensitive)", value=r"^(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", key='kw_pattern', disabled=not use_keywords, help="e.g., `CHAPTER \\d+` or `Introduction|Conclusion`")

# --- Chunking Mode & Page Num Toggle ---
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

        # --- Compile Heading Criteria Dictionary ---
        # (Make sure all variables like require_bold etc. are defined from UI above)
        heading_criteria = {
            "require_bold": require_bold if use_style else False,
            "require_italic": require_italic if use_style else False,
            "require_title_case": require_title_case if use_case else False,
            "require_all_caps": require_all_caps if use_case else False,
            "require_centered": require_centered if use_layout else False,
            "require_isolated": require_isolated if use_layout else False,
            "min_words": min_words if use_length else 1,
            "max_words": max_words if use_length else 50, # Default high max if not used
            "keyword_pattern": keyword_pattern.strip() if use_keywords and keyword_pattern.strip() else None
            # Pass the master toggles too, in case the heuristic function needs them
            ,"use_style": use_style
            ,"use_case": use_case
            ,"use_layout": use_layout
            ,"use_length": use_length
            ,"use_keywords": use_keywords
        }

        # Validate Regex if used
        if heading_criteria["keyword_pattern"]:
             try: re.compile(heading_criteria["keyword_pattern"], re.IGNORECASE)
             except re.error as e:
                  st.error(f"Invalid Regex in Keyword Pattern: {e}"); st.stop()

        # --- Get File Info & Display Settings ---
        file_content = uploaded_file.getvalue()
        file_name = uploaded_file.name
        is_pdf = file_name.lower().endswith(".pdf")

        active_criteria_summary = [] # Build summary again
        if use_style: active_criteria_summary.append(f"Style(B:{require_bold},I:{require_italic})")
        if use_case: active_criteria_summary.append(f"Case(T:{require_title_case},A:{require_all_caps})")
        if use_layout: active_criteria_summary.append(f"Layout(C:{require_centered},I:{require_isolated})")
        if use_length: active_criteria_summary.append(f"Len({min_words}-{max_words})")
        if heading_criteria['keyword_pattern']: active_criteria_summary.append("Keyword")
        settings_info = f"Chunk Mode: '{chunk_mode}' | Include Loc#: {include_page_numbers} | Heading Criteria: {', '.join(active_criteria_summary) if active_criteria_summary else 'None Active'}"
        if is_pdf: settings_info += f" | PDF Skip: {start_skip} start, {end_skip} end | PDF Offset: {start_page_offset}"
        st.info(settings_info)

        # --- Extraction ---
        with st.spinner("Step 1: Reading file and extracting structure..."):
            start_time = time.time()
            sentences_data = extract_sentences_with_structure(
                file_name=file_name,
                file_content=file_content,
                heading_criteria=heading_criteria, # Pass the dictionary
                start_skip=int(start_skip) if is_pdf else 0,
                end_skip=int(end_skip) if is_pdf else 0,
                start_page_offset=int(start_page_offset) if is_pdf else 1
            )
            extract_time = time.time() - start_time
            st.write(f"Extraction took: {extract_time:.2f} seconds")

        # --- Chunking and Output ---
        if sentences_data is None: st.error("Failed to extract data.")
        elif not sentences_data: st.warning("No text content found.")
        else:
            st.success(f"Extracted {len(sentences_data)} items.")
            # --- Conditional Chunking ---
            # (Keep the rest of the chunking/output logic exactly as in v15)
            if chunk_mode == 'Chunk by Detected Chapter Title':
                with st.spinner("Step 2: Chunking by chapter title..."):
                    start_time = time.time()
                    # Assumes extract_sentences returns (text, marker, chapter_title_or_None)
                    chunk_list = chunk_by_chapter(sentences_data) # Needs the right input format
                    chunk_time = time.time() - start_time
                    st.write(f"Chapter chunking took: {chunk_time:.2f} seconds")
                output_columns = ['title', 'chunk_text']
            else: # Default to token-based chunking
                 with st.spinner(f"Step 2: Chunking into ~{TARGET_TOKENS} token chunks..."):
                    start_time = time.time()
                    # Assumes extract_sentences returns (text, marker, chapter_title_or_None)
                    # This call assumes chunker handles 3-item tuples
                    chunk_list = chunk_structured_sentences(
                        sentences_data, tokenizer, TARGET_TOKENS, OVERLAP_SENTENCES
                    )
                    chunk_time = time.time() - start_time
                    st.write(f"Token chunking took: {chunk_time:.2f} seconds")
                 output_columns = ['chunk_text', 'page_number', 'title']

            # --- Process Results ---
            if chunk_list:
                st.success(f"Processing complete. Generated {len(chunk_list)} chunks.")
                df = pd.DataFrame(chunk_list)
                if 'title' not in df.columns: df['title'] = "Unknown"
                df['title'] = df['title'].fillna("Unknown Chapter / Front Matter")

                final_columns = []
                if 'chunk_text' in df.columns: final_columns.append('chunk_text')
                if include_page_numbers and 'page_number' in df.columns: final_columns.append('page_number')
                if 'title' in df.columns: final_columns.append('title')

                if not final_columns or 'chunk_text' not in final_columns : st.error("Error processing columns.")
                else:
                    df_display = df[final_columns]
                    st.dataframe(df_display)
                    csv_data = df_display.to_csv(index=False).encode('utf-8')
                    st.download_button( label="Download data as CSV", data=csv_data,
                        file_name=f'{uploaded_file.name}_chunks_v15.csv', mime='text/csv', key="download_csv_v15"
                    )
            else: st.error("Chunking resulted in no data.")


# --- END OF FILE app.py ---
