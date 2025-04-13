import fitz
import re
import nltk
import statistics
import streamlit as st

# --- NLTK Download Logic ---
# (Keep as is)
def download_nltk_data(resource_name, resource_path):
    try:
        nltk.data.find(resource_path)
    except LookupError:
        st.info(f"Downloading NLTK data package: '{resource_name}'...")
        try:
            nltk.download(resource_name, quiet=True)
            st.success(f"NLTK data '{resource_name}' downloaded.")
            return True
        except Exception as e:
            st.error(f"Download Error: Failed to download NLTK '{resource_name}' data: {e}")
            return False
    except Exception as e_find:
        st.error(f"NLTK Find Error: An error occurred checking for NLTK data '{resource_name}': {e_find}")
        return False
    return True


# --- Metadata/Footer Check ---
# (Keep as is, but you might need to add more specific rules for your PDF)
def is_likely_metadata_or_footer(line):
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

# --- Final Simplified Heading Checker ---
def check_heading_heuristics_final(line_dict, page_width, is_single_line_block):
    """
    Focuses on: Short lines, centered (approx), alone in block, with title case/style.
    Returns ('chapter', text) or (None, None). Does not differentiate subchapters.
    """
    line_text = "".join(s["text"] for s in line_dict["spans"]).strip()
    words = line_text.split()
    num_words = len(words)

    if not line_text or num_words == 0: return None, None
    if is_likely_metadata_or_footer(line_text): return None, None

    # --- Configuration (Tune these) ---
    MAX_HEADING_WORDS = 8
    MIN_HEADING_WORDS = 2
    CENTER_TOLERANCE_RATIO = 0.15 # % diff between left/right margin
    MIN_MARGIN_RATIO = 0.15 # % page width that must be margin on each side

    # --- Check Basic Criteria ---
    is_short = MIN_HEADING_WORDS <= num_words <= MAX_HEADING_WORDS
    has_no_end_punctuation = not line_text[-1] in ['.', '?', '!', ':', ',', ';']

    # --- Check Centering (Approximate) ---
    line_bbox = line_dict.get('bbox', None)
    is_centered_hint = False
    if line_bbox and page_width > 0:
        left_margin = line_bbox[0]
        right_margin = page_width - line_bbox[2]
        if abs(left_margin - right_margin) < (page_width * CENTER_TOLERANCE_RATIO) and \
           left_margin > (page_width * MIN_MARGIN_RATIO) and \
           right_margin > (page_width * MIN_MARGIN_RATIO):
            is_centered_hint = True

    # --- Check Style/Case ---
    is_title_case = line_text.istitle()
    is_italic_hint = False
    try: # Check first span font name for italic
        if line_dict["spans"] and "italic" in line_dict["spans"][0].get('font', '').lower():
            is_italic_hint = True
    except Exception: pass

    # --- Decision Logic ---
    # Primary Trigger: Line is alone in its block, centered, short, and looks like a title
    if is_single_line_block and is_centered_hint and is_short and has_no_end_punctuation:
        # Extra check: Must be Title Case OR Italic
        if is_title_case or is_italic_hint:
             # Check it contains letters
            if re.search("[a-zA-Z]", line_text):
                 # print(f"✅ CH (Layout+Style/Case): {line_text}") # Debug
                 return 'chapter', line_text

    # Fallback: Explicit keywords (still useful)
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", line_text, re.IGNORECASE) and num_words < 8:
        # print(f"✅ CH (Keyword): {line_text}") # Debug
        return 'chapter', line_text


    return None, None # Not detected

# --- Main Extraction Function (Using the final checker) ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    """
    Extracts text, cleans, splits sentences, tracks pages & detects headings using layout heuristics.
    """
    doc = None
    extracted_data = []
    current_chapter_title_state = None # Track last detected chapter

    try:
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")
        total_pages = len(doc)

        for page_num_0based, page in enumerate(doc):
            if page_num_0based < start_skip: continue
            if page_num_0based >= total_pages - end_skip: break
            adjusted_page_num = page_num_0based - start_skip + start_page_offset
            page_width = page.rect.width

            try:
                # Use get_text("dict") to access line and block info
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
                for b_idx, b in enumerate(blocks):
                    if b['type'] == 0: # Text block
                        block_lines = b['lines']
                        is_single_line_block = len(block_lines) == 1

                        for l_idx, l in enumerate(block_lines):
                            line_dict = l
                            line_text = "".join(s["text"] for s in l["spans"]).strip()

                            if not line_text or is_likely_metadata_or_footer(line_text): continue

                            # --- Check Heading ---
                            # Pass the line dict, page width, and whether it's alone in its block
                            heading_type, heading_text = check_heading_heuristics_final(
                                line_dict,
                                page_width,
                                is_single_line_block
                            )

                            is_heading = heading_type is not None

                            if heading_type == 'chapter':
                                current_chapter_title_state = heading_text
                                extracted_data.append((heading_text, adjusted_page_num, heading_text, None)) # Chapter tuple
                            # NOTE: This simple version does NOT detect subchapters
                            else: # Regular text
                                try:
                                    sentences_in_line = nltk.sent_tokenize(line_text)
                                    for sentence in sentences_in_line:
                                        sentence_clean = sentence.strip()
                                        if sentence_clean:
                                            extracted_data.append((sentence_clean, adjusted_page_num, None, None)) # Text tuple
                                except Exception as e_nltk:
                                    st.warning(f"NLTK Error (Page {adjusted_page_num}): Line '{line_text}'. Error: {e_nltk}")
                                    if line_text: # Append raw line as fallback
                                        extracted_data.append((line_text, adjusted_page_num, None, None))

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
