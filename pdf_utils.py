import fitz
import re
import nltk
import streamlit as st

# --- NLTK Download Logic ---
def download_nltk_data(resource_name, resource_path):
    # ...(keep as is)...
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
def is_likely_metadata_or_footer(line):", line_text, re.IGNORECASE) and num_words < 8:
        return 'chapter', line_text

    # 2. Style (Italic/Bold Hint) + Title Case + Short = Likely Chapter
    # This combination strongly matches your examples
    if (is_italic_hint or is_bold_hint) and is_title_case and MIN_HEADING_WORDS <= num_words <= MAX_HEADING_WORDS:
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']: # Check punctuation
              # print(f"✅ CH (Style+Case+Len): {line_text}") # Debug
              return 'chapter', line_text

    # 3. Just Title Case + Short = Possibly Subchapter (if in chapter) or Chapter (if not)
    if is_title_case and MIN_HEADING_WORDS <= num_words <= MAX_HEADING_WORDS + 2: # Allow slightly longer for sub
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
             if current_chapter_title:
                  # print(f"✅ SUB (Case+Len): {line_text}") # Debug
                  return 'subchapter', line_text
             else:
                  # print(f"✅ CH (Case+Len Fallback): {line_text}") # Debug
                  return 'chapter', line_text # Assume chapter if no context


    # 4. Numbered list items - Treat as chapter for now
    if re.match(r"^\s*[IVXLCDM]+\.?\s+.{3,}", line_text) and num_words < 10: return 'chapter', line_text
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line_text) and num_words < 8: return 'chapter', line_text


    return None, None # Not detected as heading


# --- Main Extraction Function (Using the new checker) ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    
    # ...(keep as is)...
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

# --- VERY Simplified Heading Checker ---
def check_heading_layout_only(block_text, block_bbox, page_width):
    """
    Checks ONLY if the block is a single, short, centered line.
    Returns ('chapter', text) or (None, None).
    """
    # 1. Check if it's a single line block (no internal newlines after stripping)
    block_text_stripped = block_text.strip()
    if '\n' in block_text_stripped:
        return None, None # Not a single line

    # 2. Check Length
    words = block_text_stripped.split()
    num_words = len(words)
    # --- Tunable Parameters ---
    MAX_HEADING_WORDS = 9
    MIN_HEADING_WORDS = 1 # Allow single word headings if centered
    CENTER_TOLERANCE_RATIO = 0.18 # Allow more tolerance
    MIN_MARGIN_RATIO = 0.15
    # --- End Tuning ---
    is_short = MIN_HEADING_WORDS <= num_words <= MAX_HEADING_WORDS

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

            try:
                # Use get_text("dict") for span info (font names/flags)
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
                for b in blocks:
                    if b['type'] == 0: # Text block
                        for l in b["lines"]:
                            line_dict = l # Pass the whole line dictionary
                            line_text = "".join(s["text"] for s in l["spans"]).strip()

                            if not line_text or is_likely_metadata_or_footer(line_text    # 3. Check Centering (Approximate)
    is_centered_hint = False
    if block_bbox and page_width > 0:
        left_margin = block_bbox[0]
        right_margin = page_width - block_bbox[2]
        # Check if margins are roughly equal and significant
        if abs(left_margin - right_margin) < (page_width * CENTER_TOLERANCE_RATIO) and \
           left_margin > (page_width * MIN_MARGIN_RATIO) and \
           right_margin > (page_width * MIN_MARGIN_RATIO):
            is_centered_hint = True

    # 4. Decision: If single line, short, and centered -> Chapter
    if is_short and is_centered_hint:
        # Check it contains actual letters
        if re.search("[a-zA-Z]", block_text_stripped):
            # print(f"✅ CH (Layout): {block_text_stripped}") # Debug
            return 'chapter', block_text_stripped

    return None, None


# --- Main Extraction Function (Using get_text("blocks")) ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    doc = None
    extracted_data = []
    current_chapter_title_state = None # Still track last detected chapter

    try:
        doc): continue

                            # --- Check Heading ---
                            heading_type, heading_text = check_heading_heuristics_v8(
                                line_dict,
                                current_chapter_title_state
                            )

                            is_heading = heading_type is not None

                            if heading_type == 'chapter':
                                current_chapter_title_state = heading_text # Update state
                                extracted_data.append((heading_text, adjusted_page_num, heading_text, None))
                            elif heading_type == 'subchapter':
                                # Subchapter heading text IS included in the data stream
                                extracted_data.append((heading_text, adjusted_page_num, None, heading_text))
                            else: # Regular text
                                try:
                                    sentences_in_line = nltk.sent_tokenize(line_text)
                                    for sentence in sentences_ = fitz.open(stream=uploaded_file_content, filetype="pdf")
        total_pages = len(doc)

        for page_num_0based, page in enumerate(doc):
            # Page Skipping
            if page_num_0based < start_skip: continue
            if page_num_0based >= total_pages - end_skip: break
            adjusted_page_num = page_num_0based - start_skip + start_page_offset
            page_width = page.rect.width

            try:
                # Get text as blocks: [x0, y0, x1, y1, "text content...\n...", block_no, block_type]
                blocks = page.get_text("blocks", sort=Truein_line:
                                        sentence_clean = sentence.strip()
                                        if sentence_clean:
                                            extracted_data.append((sentence_clean, adjusted_page_num, None, None))
                                except Exception as e_nltk:
                                    st.warning(f"NLTK Error (Page)

                for b in blocks:
                    block_text = b[4] # The text content of the block
                    block_bbox = b[:4] # The bounding box
                    block_text_clean = block_text.strip() # {adjusted_page_num}): Line '{line_text}'. Error: {e_nltk}")
                                    if line_text: extracted_data.append((line_ For checking if block is empty

                    if not block_text_clean or is_likely_metadata_or_footer(block_text_clean):
                        continue

text, adjusted_page_num, None, None))

            except Exception as e_page                    # Check if this block qualifies as a heading based on layout
                    heading_type:
                 st.error(f"Processing Error: Failed to process page {adjusted_page_num}. Error: {e_page}")
                 continue

, heading_text = check_heading_by_layout(
                        block        return extracted_data

    except Exception as e_main:
        st.error(f"Main Extraction Error: An unexpected error occurred: {_text, # Pass the raw block text
                        block_bbox,
e_main}")
        st.exception(e_main)
        return None
    finally:
        if doc: doc.close()
