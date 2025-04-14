# --- START OF FILE chunker.py ---
import tiktoken

def chunk_structured_sentences(sentences_structure, tokenizer, target_tokens, overlap_sentences    require_italic = st.checkbox("Must be Italic?", value=True, key='req_italic', disabled=not use_style)

):
    """
    Chunks sentences/headings based on tokens, assigns last known chapter title.
    Input: List of (text, page_num_# Case
use_case = st.sidebar.checkbox("Check Text Case?", value=marker, detected_chapter_title) tuples.
    Output: List of dictionaries [{'chunkTrue, key='use_case')
col1a, col2a = st._text': ..., 'page_number': ..., 'title': ...}]
sidebar.columns(2)
with col1a:
    require_title_case = st.checkbox("Must be Title Case?", value=True,    """
    if not tokenizer: print("ERROR: Tokenizer not provided."); return []
    if not sentences_structure: print("Warning: No sentences provided."); return []

    chunks_data = []
    current_chunk_texts key='req_title', disabled=not use_case)
with col2a: = []
    current_chunk_pages = []
    current_chunk
    require_all_caps = st.checkbox("Must be ALL CAPS?", value=False, key='req_caps', disabled=not use_case)
_tokens = 0
    current_chapter = "Unknown Chapter / Front Matter"

    # Indices of content items (where detected_chapter_title    if require_title_case and require_all_caps and use_case: is None)
    content_indices = [i for i, (_, _, ch) in enumerate(sentences_structure) if ch is None]

    def finalize
         st.sidebar.warning("Title Case and ALL CAPS selected - heading_chunk():
        nonlocal chunks_data, current_chunk_texts must match both.", icon="⚠️")

# Layout
use_layout = st.sidebar.checkbox("Check Layout?", value=True, key='use, current_chunk_pages, current_chunk_tokens, current_chapter_layout')
col1b, col2b = st.sidebar.columns(2
        if current_chunk_texts:
            chunk_text_joined = " ".join(current_chunk_texts).strip()
            start)
with col1b:
    require_centered = st.checkbox("Must be Centered (Approx)?", value=True, key='req_center', disabled=not use_layout)
with col2b:_marker = current_chunk_pages[0] if current_chunk_pages else "N/A"
            if chunk_text_joined:
    require_isolated = st.checkbox("Must be Alone in Block?", value=True, key='req_isolate', disabled=not use_layout
                chunks_data.append({
                    "chunk_text": chunk, help="Checks if heading is the only line in its paragraph/block (PDF only).")

# Length
use_length = st.sidebar.checkbox("Check Word_text_joined,
                    "page_number": start_marker, Count?", value=True, key='use_length')
col1c, col2
                    "title": current_chapter # Use 'title' as the key
c = st.sidebar.columns(2)
with col1c:                })
            current_chunk_texts, current_chunk_pages,
    min_words = st.number_input("Min Words", min_ current_chunk_tokens = [], [], 0

    current_content_value=1, value=1, step=1, key='min_w', disabled=not use_length)
with col2c:
    max_item_index = 0

    while current_content_item_indexwords = st.number_input("Max Words", min_value=1 < len(content_indices):
        original_list_index = content_indices[current_content_item_index]

        # Find most, value=10, step=1, key='max_w', recent chapter heading before this item
        temp_chapter = current_chapter
 disabled=not use_length)

# Keywords
use_keywords = st.sidebar        for j in range(original_list_index, -1, -1): #.checkbox("Check for Keywords/Pattern?", value=True, key='use_kw')
keyword_pattern = st.text_input("Regex Pattern (optional Iterate backwards from current item
            _, _, ch_title_lookup = sentences_structure[j] # Unpack 3 items
            if ch_title_lookup is not None:
                temp_chapter = ch_title_lookup
                break

        # If chapter changed *before* this content item started
        , case-insensitive)", value=r"^(CHAPTER|SECTION|PART)\s+[if temp_chapter != current_chapter:
            finalize_chunk() # Finalize chunk under old chapter
            current_chapter = temp_chapter #IVXLCDM\d]+", key='kw_pattern', disabled=not use_keywords, help="e.g., `CHAPTER \\d+` or Update to the new chapter

        # Process the content item
        text, page_marker `Introduction|Conclusion`")

# --- Chunking Mode ---
st.sidebar.subheader("Chunking Method")
chunk_mode = st.sidebar.radio(, _ = sentences_structure[original_list_index] # Unpack 3 items
    "Select Chunking Mode:",
    ('Chunk by ~200 Tokens (with overlap)', 'Chunk by Detected Chapter Title'),
    key='chunk
        try: sentence_tokens = len(tokenizer.encode(text))_mode_select_v15'
)
include_page_
        except Exception as e: print(f"Tokenize Error: {numbers = st.sidebar.checkbox("Include Page/Para Marker?", value=True,e}"); current_content_item_index += 1; continue

         key='page_num_toggle_v15')

# --- PDF Specific Options ---
st.sidebar.markdown("---")
st.sidebar# Check chunk boundary condition
        if current_chunk_texts and \
.markdown("**PDF Specific Options (ignored for DOCX):**")
start           ((current_chunk_tokens + sentence_tokens > target_tokens and sentence_tokens < target_tokens) or sentence_tokens >= target_tokens):
             finalize_chunk()

             # Overlap Logic
             overlap_start_skip = st.sidebar.number_input("Pages to Skip at START_content_idx = max(0, current_content_item_index - overlap_sentences)
             for k in range(overlap_start_", min_value=0, value=0, step=1)
content_idx, current_content_item_index):
                 overlap_original_idxend_skip = st.sidebar.number_input("Pages to Skip at = content_indices[k]
                 if overlap_original_idx < END", min_value=0, value=0, step=1) len(sentences_structure):
                     o_text, o_marker,
start_page_offset = st.sidebar.number_input("Actual _ = sentences_structure[overlap_original_idx] # Unpack  Page # of FIRST Processed Page", min_value=1, value=3
                     try:
                         o_tokens = len(tokenizer.encode1, step=1)


# --- Main App Logic ---
if not(o_text))
                         current_chunk_texts.append(o tokenizer: st.error("Tokenizer could not be loaded.")
elif not nltk_ready: st.error("NLTK 'punkt' data could not_text)
                         current_chunk_pages.append(o_marker)
                         current_chunk_tokens += o_tokens
                     except Exception be verified/downloaded.")
elif uploaded_file is not None:
 as e: print(f"Error encoding overlap: {e}")
                 else: print(f"Warn: Overlap index {overlap_original_    if st.button("Process File", key="chunk_button_vidx} OOB.")

        # Add current text if not exactly duplicated by overlap ending
15"):
        pdf_content = uploaded_file.getvalue()
        file        if not current_chunk_texts or text != current_chunk_texts[-1_name = uploaded_file.name
        is_pdf = file_]:
            current_chunk_texts.append(text)
            currentname.lower().endswith(".pdf")

        # --- Compile Heading Criteria ---
_chunk_pages.append(page_marker)
            current_chunk_tokens += sentence_tokens
        elif not current_chunk_pages or        heading_criteria = {
            "require_bold": use_style page_marker != current_chunk_pages[-1]:
             current_chunk_pages.append(page_marker) # Still add page marker if text was duplicate

        current_content_item_index += 1

    finalize and require_bold,
            "require_italic": use_style and_chunk() # Add last chunk
    return chunks_data

# --- Function for Chapter-based Chunking ---
def chunk_by_chapter(sentences require_italic,
            "require_title_case": use_case_structure):
    """
    Groups all text under the most recently detected chapter title and require_title_case,
            "require_all_caps":.
    Input: List of (text, page_num_marker, detected_chapter_title) tuples.
    Output: List of dictionaries [{' use_case and require_all_caps,
            "require_centeredtitle': chapter_title, 'chunk_text': all_text_for_chapter}]
    """
    if not sentences_structure: return []

    chunks": use_layout and require_centered,
            "require_isolated":_by_chapter = {}
    current_chapter = "Unknown Chapter / use_layout and require_isolated,
            "min_words": min Front Matter"

    for text, _, detected_title in sentences_structure:_words if use_length else 1, # Use defaults if length not checked
             # Unpack 3 items
        if detected_title is not None:
            "max_words": max_words if use_length else 50, # Use defaults if length not checked
            "keyword_pattern": keyword_pattern.stripcurrent_chapter = detected_title
            if current_chapter not in chunks_by_chapter:
                 chunks_by_chapter[current_chapter] = []() if use_keywords and keyword_pattern.strip() else None
        }
        # Basic validation for keyword regex
        if heading_criteria["
        else: # Only append non-heading text
            if current_chapter notkeyword_pattern"]:
             try: re.compile(heading_criteria["keyword in chunks_by_chapter:
                 chunks_by_chapter[current_pattern"], re.IGNORECASE)
             except re.error as e:
                  _chapter] = []
            chunks_by_chapter[current_chapterst.error(f"Invalid Regex in Keyword Pattern: {e}")
                  st.stop() # Stop processing if regex is invalid


        # Display Settings].append(text)

    # Format the output
    output_list = []
        settings_info = f"Chunk Mode: '{chunk_mode}' | Include
    for title, texts in chunks_by_chapter.items():
        if texts:
            output_list.append({
                "title Loc#: {include_page_numbers}"
        if is_pdf:
": title,
                "chunk_text": " ".join(texts).            settings_info += f" | PDF Skip: {start_skip}strip()
            })
    return output_list

# --- END OF start, {end_skip} end | PDF Offset: {start_page_offset FILE chunker.py ---
