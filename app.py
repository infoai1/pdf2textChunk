import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import tiktoken
import re
import nltk
import statistics
import time

# --- NLTK Download Logic ---
# Wrap in a function to avoid cluttering the main script body

# --- NLTK Download Logic ---
@st.cache_resource # Cache the download status
def ensure_nltk_data():
    data_ok = True
    # Check for punkt
    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        st.info("Downloading NLTK data package: 'punkt'...")
        try:
            nltk.download('punkt', quiet=True)
            st.success("NLTK data 'punkt' downloaded.")
        except Exception as e:
            st.error(f"Download Error: Failed to download NLTK 'punkt' data: {e}")
            data_ok = False

    # Check for punkt_tab (THIS IS THE MISSING PART)
    try:
        nltk.data.find('tokenizers/punkt_tab') # Add this check
    except LookupError:
        st.info("Downloading NLTK data package: 'punkt_tab'...") # Add this download block
        try:
            nltk.download('punkt_tab', quiet=True)
            st.success("NLTK data 'punkt_tab' downloaded.")
        except Exception as e:
            st.error(f"Download Error: Failed to download NLTK 'punkt_tab' data: {e}")
            data_ok = False # Consider if critical, maybe okay to proceed without?

    except Exception as e_find: # General find error
        st.error(f"NLTK Find Error: An error occurred checking for NLTK data: {e_find}")
        data_ok = False

    return data_ok # Return overall status
# --- Tokenizer Setup ---
@st.cache_resource
def get_tokenizer():
    try: return tiktoken.get_encoding("cl100k_base")
    except Exception as e: st.error(f"Error initializing tokenizer: {e}"); return None

# --- PDF Utility Functions ---

def is_likely_metadata_or_footer(line):
    # (Using the robust version from previous steps)
    line = line.strip()
    if not line: return True
    cleaned_line = re.sub(r"^\W+|\W+$", "", line)
    if cleaned_line.isdigit() and line == cleaned_line and len(cleaned_line) < 4 : return True
    if "www." in line or ".com" in line or "@" in line or "books" in line.lower() or "global" in line.lower() or ("center" in line.lower() and "peace" in line.lower()):
         if len(line.split()) < 10: return True
    if re.match(r"^\s*Page\s+\d+\s*$", line, re.IGNORECASE): return True
    if "©" in line or "copyright" in line.lower() or "first published" in line.lower() or "isbn" in line.lower(): return True
    if "printed in" in line.lower(): return True
    if any(loc in line.lower() for loc in ["nizamuddin", "new delhi", "noida", "bensalem", "byberry road"]): return True
    if len(set(line.strip())) < 4 and len(line.strip()) > 4: return True
    if line.endswith(cleaned_line) and cleaned_line.isdigit() and len(line) < 80 and len(line) > len(cleaned_line) + 2:
         if not re.search(r"[a-zA-Z]{4,}", line): return True
    return False

def check_heading_heuristics_simple(line_dict, current_chapter_title):
    """ Simplified heuristic focusing on Italic/Bold flags, Title Case, and Length. """
    line_text = "".join(s["text"] for s in line_dict["spans"]).strip()
    words = line_text.split()
    num_words = len(words)

    if not line_text or num_words == 0: return None, None
    if is_likely_metadata_or_footer(line_text): return None, None

    is_italic_hint = False
    is_bold_hint = False
    is_title_case = line_text.istitle()

    try: # Check first span font name for style hints
        if line_dict["spans"]:
            font_name = line_dict["spans"][0].get('font', '').lower()
            is_italic_hint = "italic" in font_name
            is_bold_hint = "bold" in font_name or "black" in font_name
    except Exception: pass

    MAX_HEADING_WORDS = 9
    MIN_HEADING_WORDS = 2

    # Rule 1: Explicit Keywords
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", line_text, re.IGNORECASE) and num_words < 8:
        return 'chapter', line_text

    # Rule 2: Style + Title Case + Short (Likely Chapter)
    if (is_italic_hint or is_bold_hint) and is_title_case and MIN_HEADING_WORDS <= num_words <= MAX_HEADING_WORDS:
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
              return 'chapter', line_text

    # Rule 3: Title Case + Short (Subchapter/Chapter Fallback)
    if is_title_case and MIN_HEADING_WORDS <= num_words <= MAX_HEADING_WORDS + 2:
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
             if current_chapter_title: return 'subchapter', line_text
             else: return 'chapter', line_text

    # Rule 4: Numbered lists
    if re.match(r"^\s*[IVXLCDM]+\.?\s+.{3,}", line_text) and num_words < 10: return 'chapter', line_text
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line_text) and num_words < 8: return 'chapter', line_text

    return None, None # Not detected

def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    doc = None
    extracted_data = []
    current_chapter_title_state = None

    try:
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")
        total_pages = len(doc)

        for page_num_0based, page in enumerate(doc):
            if page_num_0based < start_skip: continue
            if page_num_0based >= total_pages - end_skip: break
            adjusted_page_num = page_num_0based - start_skip + start_page_offset

            try:
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_PRESERVE_LIGATURES)["blocks"] # Using dict
                for b in blocks:
                    if b['type'] == 0: # Text block
                        for l in b["lines"]:
                            line_dict = l
                            line_text = "".join(s["text"] for s in l["spans"]).strip()

                            if not line_text or is_likely_metadata_or_footer(line_text): continue

                            heading_type, heading_text = check_heading_heuristics_simple(
                                line_dict,
                                current_chapter_title_state
                            )

                            is_heading = heading_type is not None

                            if heading_type == 'chapter':
                                current_chapter_title_state = heading_text
                                extracted_data.append((heading_text, adjusted_page_num, heading_text, None))
                            elif heading_type == 'subchapter':
                                extracted_data.append((heading_text, adjusted_page_num, None, heading_text))
                            else: # Regular text
                                try:
                                    sentences_in_line = nltk.sent_tokenize(line_text)
                                    for sentence in sentences_in_line:
                                        sentence_clean = sentence.strip()
                                        if sentence_clean:
                                            extracted_data.append((sentence_clean, adjusted_page_num, None, None))
                                except Exception as e_nltk:
                                    st.warning(f"NLTK Error (Page {adjusted_page_num}): Line '{line_text}'. Error: {e_nltk}")
                                    if line_text: extracted_data.append((line_text, adjusted_page_num, None, None))

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


# --- Chunker Function (Copied into app.py) ---
def chunk_structured_sentences(sentences_structure, tokenizer, target_tokens, overlap_sentences):
    if not tokenizer: print("ERROR: Tokenizer not provided."); return []
    if not sentences_structure: print("Warning: No sentences provided."); return []

    chunks_data = []
    current_chunk_texts = []
    current_chunk_pages = []
    current_chunk_tokens = 0
    current_chapter = "Unknown Chapter / Front Matter"
    current_subchapter = None

    content_indices = [i for i, (_, _, ch, _) in enumerate(sentences_structure) if ch is None]

    def finalize_chunk():
        nonlocal chunks_data, current_chunk_texts, current_chunk_pages, current_chunk_tokens, current_chapter, current_subchapter
        if current_chunk_texts:
            chunk_text_joined = " ".join(current_chunk_texts).strip()
            start_page = current_chunk_pages[0] if current_chunk_pages else 0
            if chunk_text_joined:
                chunks_data.append({
                    "chunk_text": chunk_text_joined,
                    "page_number": start_page,
                    "chapter_title": current_chapter,
                    "subchapter_title": current_subchapter
                })
            current_chunk_texts = []
            current_chunk_pages = []
            current_chunk_tokens = 0

    current_content_item_index = 0

    while current_content_item_index < len(content_indices):
        original_list_index = content_indices[current_content_item_index]

        # Find most recent chapter/subchapter state *before* this content item
        temp_chapter = current_chapter
        temp_subchapter = current_subchapter
        found_sub_after_last_chap = False
        for j in range(original_list_index, -1, -1):
            _, _, ch_title_lookup, sub_title_lookup = sentences_structure[j]
            if ch_title_lookup is not None:
                temp_chapter = ch_title_lookup
                if not found_sub_after_last_chap: temp_subchapter = None
                break
            if sub_title_lookup is not None and not found_sub_after_last_chap:
                 temp_subchapter = sub_title_lookup
                 found_sub_after_last_chap = True

        # Finalize chunk if chapter changed before this content item
        if temp_chapter != current_chapter:
            finalize_chunk()
            current_chapter = temp_chapter
            current_subchapter = temp_subchapter # Apply subchapter belonging to new chapter
        elif temp_subchapter != current_subchapter:
            current_subchapter = temp_subchapter # Update if only subchapter changed

        # Process the actual content item
        text, page_num, _, _ = sentences_structure[original_list_index]
        sentence_tokens = len(tokenizer.encode(text))

        # Check chunk boundary
        if current_chunk_texts and \
           ((current_chunk_tokens + sentence_tokens > target_tokens and sentence_tokens < target_tokens*0.8) or sentence_tokens >= target_tokens*1.5):
            finalize_chunk()

            # --- Overlap Logic ---
            overlap_start_content_idx = max(0, current_content_item_index - overlap_sentences)
            for k in range(overlap_start_content_idx, current_content_item_index):
                 overlap_original_idx = content_indices[k]
                 if overlap_original_idx < len(sentences_structure):
                     o_text, o_page, _, _ = sentences_structure[overlap_original_idx]
                     # --- THIS IS THE BLOCK WHERE THE ERROR OCCURS ---
                     # Ensure indentation is correct here (4 spaces relative to 'if' above)
                     o_tokens = len(tokenizer.encode(o_text)) # LINE 7 Error reported here originally
                     current_chunk_texts.append(o_text)
                     current_chunk_pages.append(o_page)
                     current_chunk_tokens += o_tokens
                 else:
                     print(f"Warning: Overlap index {overlap_original_idx} out of bounds.")
            # --- End Overlap Logic ---

        # Add current text to the chunk
        current_chunk_texts.append(text)
        current_chunk_pages.append(page_num)
        current_chunk_tokens += sentence_tokens

        current_content_item_index += 1

    finalize_chunk() # Add last chunk
    return chunks_data

# --- Constants ---
TARGET_TOKENS = 200
OVERLAP_SENTENCES = 2 # Use 2 sentences for ~10-15% overlap approx

# --- Ensure NLTK data is available ---
nltk_ready = ensure_nltk_data()

# --- Tokenizer Setup ---
tokenizer = get_tokenizer()

# --- Streamlit App UI ---
st.title("PDF Structured Chunker v9 (Single File)")
st.write("Upload PDF, specify skips/offset. Attempts heading detection based on style, case, length.")

uploaded_file = st.file_uploader("1. Upload Book PDF", type="pdf", key="pdf_uploader_v9")

st.sidebar.header("Processing Options")
start_skip = st.sidebar.number_input("Pages to Skip at START", min_value=0, value=0, step=1)
end_skip = st.sidebar.number_input("Pages to Skip at END", min_value=0, value=0, step=1)
start_page_offset = st.sidebar.number_input("Actual Page # of FIRST Processed Page", min_value=1, value=1, step=1)

if not tokenizer:
    st.error("Tokenizer could not be loaded.")
elif not nltk_ready:
     st.error("NLTK 'punkt' data package could not be verified/downloaded.")
elif uploaded_file:
    if st.button("Process PDF", key="chunk_button_v9"):
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

        if sentences_data is None: st.error("Failed to extract data.")
        elif not sentences_data: st.warning("No text found after cleaning/skipping.")
        else:
            st.success(f"Extracted {len(sentences_data)} items (sentences/headings).")
            with st.spinner(f"Step 2: Chunking sentences into ~{TARGET_TOKENS} token chunks..."):
                start_time = time.time()
                chunk_list = chunk_structured_sentences(
                    sentences_data, tokenizer, TARGET_TOKENS, OVERLAP_SENTENCES
                )
                chunk_time = time.time() - start_time
                st.write(f"Chunking took: {chunk_time:.2f} seconds")

            if chunk_list:
                st.success(f"Text chunked into {len(chunk_list)} chunks.")
                df = pd.DataFrame(chunk_list, columns=['chunk_text', 'page_number', 'chapter_title', 'subchapter_title'])
                df['chapter_title'] = df['chapter_title'].fillna("Unknown Chapter / Front Matter")
                df['subchapter_title'] = df['subchapter_title'].fillna("")
                df = df.reset_index(drop=True)
                st.dataframe(df[['chunk_text', 'page_number', 'chapter_title']]) # Display main columns

                csv_data = df[['chunk_text', 'page_number', 'chapter_title']].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV", data=csv_data,
                    file_name=f'{uploaded_file.name.replace(".pdf", "")}_chunks_v9.csv',
                    mime='text/csv', key="download_csv_v9"
                )
            else: st.error("Chunking failed.")
