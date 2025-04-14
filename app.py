import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import tiktoken
import re
import nltk
import time # Although not strictly needed in this version without API calls

# --- NLTK Download Logic ---
@st.cache_resource # Cache the download status
def ensure_nltk_data():
    """Checks for and downloads NLTK data if missing."""
    data_ok = True
    resources = {'punkt': 'tokenizers/punkt', 'punkt_tab': 'tokenizers/punkt_tab'}
    for name, path in resources.items():
        try:
            nltk.data.find(path)
            # st.sidebar.success(f"NLTK '{name}' found.") # Optional success message
        except LookupError:
            st.sidebar.info(f"Downloading NLTK data package: '{name}'...")
            try:
                nltk.download(name, quiet=True)
                st.sidebar.success(f"NLTK data '{name}' downloaded.")
            except Exception as e:
                st.sidebar.error(f"Download Error: Failed for NLTK '{name}'. Error: {e}")
                data_ok = False # Mark as failed
        except Exception as e_find:
            st.sidebar.error(f"NLTK Find Error ({name}): {e_find}")
            data_ok = False
    if not data_ok:
        st.error("Essential NLTK data could not be downloaded/verified. Processing may fail.")
    return data_ok

# --- Tokenizer Setup ---
@st.cache_resource
def get_tokenizer():
    """Initializes and returns the tokenizer."""
    try: return tiktoken.get_encoding("cl100k_base")
    except Exception as e: st.error(f"Error initializing tokenizer: {e}"); return None

# --- PDF Utility Functions ---

def is_likely_metadata_or_footer(line):
    """Basic heuristic to filter out metadata/footers/page numbers."""
    line = line.strip()
    if not line: return True
    # Try to catch page numbers more reliably (allow optional surrounding chars)
    cleaned_line = re.sub(r"^\W+|\W+$", "", line)
    if cleaned_line.isdigit() and len(cleaned_line) < 4:
        return True
    # Common filtering patterns
    if "www." in line or ".com" in line or "@" in line or "books" in line.lower() or "global" in line.lower() or ("center" in line.lower() and "peace" in line.lower()):
        if len(line.split()) < 12: return True # Be a bit more generous
    if "©" in line or "copyright" in line.lower() or "first published" in line.lower() or "isbn" in line.lower(): return True
    if "printed in" in line.lower(): return True
    if any(loc in line.lower() for loc in ["nizamuddin", "new delhi", "noida", "bensalem", "byberry road"]): return True
    # Filter very short lines that aren't headings (might be remnants)
    if len(line.split()) <= 1 and len(line) < 10 and not line.isupper() and not line.istitle(): return True
    return False

def check_heading_simple_layout(block_text, block_bbox, page_width):
    """
    Checks ONLY: Is it a single line, short (2-9 words), and roughly centered?
    Returns ('chapter', text) or (None, None).
    """
    # 1. Check if it's a single line block (no internal newlines after stripping)
    block_text_stripped = block_text.strip()
    # Check for internal newlines that weren't stripped - indicating multi-line visually
    if '\n' in block_text_stripped and len(block_text_stripped.split('\n')) > 1 :
        return None, None

    # 2. Check Length
    words = block_text_stripped.split()
    num_words = len(words)
    MAX_HEADING_WORDS = 9
    MIN_HEADING_WORDS = 1 # Allow single words if strongly centered
    is_short = MIN_HEADING_WORDS <= num_words <= MAX_HEADING_WORDS

    # 3. Check Centering (Approximate)
    is_centered_hint = False
    if block_bbox and page_width > 0:
        CENTER_TOLERANCE_RATIO = 0.20 # Allow 20% difference between margins
        MIN_MARGIN_RATIO = 0.18     # Require at least 18% margin on each side
        left_margin = block_bbox[0]
        right_margin = page_width - block_bbox[2]
        if abs(left_margin - right_margin) < (page_width * CENTER_TOLERANCE_RATIO) and \
           left_margin > (page_width * MIN_MARGIN_RATIO) and \
           right_margin > (page_width * MIN_MARGIN_RATIO):
            is_centered_hint = True

    # 4. Decision: If single line, short, and centered -> Chapter
    if is_short and is_centered_hint:
        # Final check: ensure it contains letters, not just symbols/numbers
        if re.search("[a-zA-Z]", block_text_stripped):
            # print(f"✅ CH (Layout): {block_text_stripped}") # Debug
            return 'chapter', block_text_stripped

    return None, None

# --- Main Extraction Function (Simplified) ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    doc = None
    extracted_data = []
    current_chapter_title_state = "Unknown Chapter / Front Matter" # Start with default

    try:
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")
        total_pages = len(doc)

        for page_num_0based, page in enumerate(doc):
            if page_num_0based < start_skip: continue
            if page_num_0based >= total_pages - end_skip: break
            adjusted_page_num = page_num_0based - start_skip + start_page_offset
            page_width = page.rect.width

            try:
                # Use get_text("blocks") for layout info
                blocks = page.get_text("blocks", sort=True)

                for b in blocks:
                    block_bbox = b[:4] # Bounding box
                    block_text = b[4]  # Text content including newlines within block
                    block_text_clean_for_check = block_text.strip() # For metadata check

                    if not block_text_clean_for_check or is_likely_metadata_or_footer(block_text_clean_for_check):
                        continue

                    # Check if the block *looks like* a heading based on layout
                    heading_type, heading_text = check_heading_simple_layout(
                        block_text, # Pass raw block text
                        block_bbox,
                        page_width
                    )

                    if heading_type == 'chapter':
                        current_chapter_title_state = heading_text # Update state
                        # Append ONLY the heading text itself
                        extracted_data.append((heading_text, adjusted_page_num, heading_text, None))
                    else:
                        # If not a heading, process block content line by line, then sentence by sentence
                        block_lines = block_text.split('\n')
                        for line in block_lines:
                            line_cleaned_for_nltk = line.strip()
                            if not line_cleaned_for_nltk or is_likely_metadata_or_footer(line_cleaned_for_nltk): continue # Check again per line

                            try:
                                sentences = nltk.sent_tokenize(line_cleaned_for_nltk)
                                for sentence in sentences:
                                    sentence_clean = sentence.strip()
                                    if sentence_clean:
                                        # Append sentence with current chapter state
                                        extracted_data.append((sentence_clean, adjusted_page_num, None, None)) # No heading info for sentences
                            except Exception as e_nltk:
                                st.warning(f"NLTK Error (Page {adjusted_page_num}): Line '{line_cleaned_for_nltk}'. Error: {e_nltk}")
                                if line_cleaned_for_nltk: # Append raw line as fallback
                                    extracted_data.append((line_cleaned_for_nltk, adjusted_page_num, None, None))

            except Exception as e_page:
                 st.error(f"Processing Error: Failed to process page {adjusted_page_num}. Error: {e_page}")
                 continue

        return extracted_data

    except Exception as e_main:
        st.error(f"Main Extraction Error: An unexpected error occurred: {e_main}")
        st.exception(e_main)
        return None
    finally:
        if doc: doc.close()


# --- Chunker Function (Simplified for this context) ---
def chunk_structured_sentences(sentences_structure, tokenizer, target_tokens, overlap_sentences):
    if not tokenizer: print("ERROR: Tokenizer not provided."); return []
    if not sentences_structure: print("Warning: No sentences provided."); return []

    chunks_data = []
    current_chunk_texts = []
    current_chunk_pages = []
    current_chunk_tokens = 0
    current_chapter = "Unknown Chapter / Front Matter" # Initial state

    # Store indices of items that are NOT chapter headings
    content_indices = [i for i, (_, _, ch, _) in enumerate(sentences_structure) if ch is None]

    def finalize_chunk():
        nonlocal chunks_data, current_chunk_texts, current_chunk_pages, current_chunk_tokens, current_chapter
        if current_chunk_texts:
            chunk_text_joined = " ".join(current_chunk_texts).strip()
            start_page = current_chunk_pages[0] if current_chunk_pages else 0
            if chunk_text_joined:
                chunks_data.append({
                    "chunk_text": chunk_text_joined,
                    "page_number": start_page,
                    "chapter_title": current_chapter,
                    # No subchapter detection in this version
                    "subchapter_title": ""
                })
            current_chunk_texts = []
            current_chunk_pages = []
            current_chunk_tokens = 0

    current_content_item_index = 0

    while current_content_item_index < len(content_indices):
        original_list_index = content_indices[current_content_item_index]

        # Find the most recent chapter heading *before or at* this item
        temp_chapter = current_chapter
        for j in range(original_list_index, -1, -1):
            _, _, ch_title_lookup, _ = sentences_structure[j]
            if ch_title_lookup is not None:
                temp_chapter = ch_title_lookup
                break

        # If chapter changed *before* this content item started
        if temp_chapter != current_chapter:
            finalize_chunk() # Finalize chunk under old chapter
            current_chapter = temp_chapter # Update to the new chapter

        # Process the content item (sentence)
        text, page_num, _, _ = sentences_structure[original_list_index]
        sentence_tokens = len(tokenizer.encode(text))

        # Check chunk boundary condition
        if current_chunk_texts and \
           (current_chunk_tokens + sentence_tokens > target_tokens and sentence_tokens < target_tokens): # Avoid breaking for single large sentences
            finalize_chunk()

            # --- Overlap Logic ---
            overlap_start_content_idx = max(0, current_content_item_index - overlap_sentences)
            for k in range(overlap_start_content_idx, current_content_item_index):
                 overlap_original_idx = content_indices[k]
                 if overlap_original_idx < len(sentences_structure):
                     o_text, o_page, _, _ = sentences_structure[overlap_original_idx]
                     # --- The line causing the error previously ---
                     try:
                         o_tokens = len(tokenizer.encode(o_text)) # Calculate tokens
                         current_chunk_texts.append(o_text)       # Add text
                         current_chunk_pages.append(o_page)       # Add page
                         current_chunk_tokens += o_tokens          # Add tokens
                     except Exception as encode_err:
                         print(f"ERROR encoding overlap text: {encode_err} Text: '{o_text[:50]}...'")
                 else:
                     print(f"Warning: Overlap index {overlap_original_idx} out of bounds.")
            # --- End Overlap Logic ---

        # Add current text to the chunk
        # Ensure we don't add the exact same text twice if it was part of the overlap *and* the current item
        if not current_chunk_texts or text != current_chunk_texts[-1]:
             current_chunk_texts.append(text)
             current_chunk_pages.append(page_num)
             current_chunk_tokens += sentence_tokens
        elif not current_chunk_pages or page_num != current_chunk_pages[-1]: # Add page even if text is duplicate but page differs
             current_chunk_pages.append(page_num)


        current_content_item_index += 1

    finalize_chunk() # Add last chunk
    return chunks_data

# --- Constants ---
TARGET_TOKENS = 200
OVERLAP_SENTENCES = 2 # For ~10-15% overlap

# --- Run NLTK Check ---
nltk_ready = ensure_nltk_data()

# --- Get Tokenizer ---
tokenizer = get_tokenizer()

# --- Streamlit App UI ---
st.title("PDF Layout Chunker v10 (Simplified)")
st.write("Focuses on short, centered lines isolated in blocks as potential chapter headings.")

uploaded_file = st.file_uploader("1. Upload Book PDF", type="pdf", key="pdf_uploader_v10")

st.sidebar.header("Processing Options")
start_skip = st.sidebar.number_input("Pages to Skip at START", min_value=0, value=0, step=1)
end_skip = st.sidebar.number_input("Pages to Skip at END", min_value=0, value=0, step=1)
start_page_offset = st.sidebar.number_input("Actual Page # of FIRST Processed Page", min_value=1, value=1, step=1)

if not tokenizer:
    st.error("Tokenizer could not be loaded.")
elif not nltk_ready:
     st.error("NLTK 'punkt' data could not be verified/downloaded.")
elif uploaded_file:
    if st.button("Process PDF", key="chunk_button_v10"):
        pdf_content = uploaded_file.getvalue()
        st.info(f"Settings: Skip first {start_skip}, Skip last {end_skip}, Start numbering from page {start_page_offset}")

        with st.spinner("Step 1: Reading PDF & detecting structure..."):
            start_time = time.time()
            sentences_data = extract_sentences_with_structure(
                pdf_content, int(start_skip), int(end_skip), int(start_page_offset)
            )
            extract_time = time.time() - start_time
            st.write(f"Extraction took: {extract_time:.2f} seconds")

        if sentences_data is None: st.error("Failed to extract data.")
        elif not sentences_data: st.warning("No text found.")
        else:
            st.success(f"Extracted {len(sentences_data)} items (sentences/headings).")
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
                df['subchapter_title'] = "" # No subchapter detection here
                df = df.reset_index(drop=True)
                st.dataframe(df[['chunk_text', 'page_number', 'chapter_title']]) # Display main columns

                csv_data = df[['chunk_text', 'page_number', 'chapter_title']].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV", data=csv_data,
                    file_name=f'{uploaded_file.name.replace(".pdf", "")}_layout_chunks_v10.csv',
                    mime='text/csv', key="download_csv_v10"
                )
            else: st.error("Chunking failed.")
