import fitz
import re
import nltk
import streamlit as st

# --- NLTK Download Logic ---
def download_nltk_data(resource_name, resource_path):
    # ... (Keep as is) ...
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
def is_likely_metadata_or_footer(line):
    # ... (Keep as is) ...
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

# --- Simplified Heading Detection ---
def check_heading_by_layout(line_dict, page_width):
    """
    VERY simple heuristic: Check if line is short, centered (approx), and alone in its block.
    Returns ('chapter', text) or (None, None). Does not differentiate subchapters.
    """
    line_text = "".join(s["text"] for s in line_dict["spans"]).strip()
    words = line_text.split()
    num_words = len(words)

    if not line_text or num_words == 0: return None, None
    if is_likely_metadata_or_footer(line_text): return None, None

    # 1. Check Length
    is_short = 1 < num_words < 8 # Adjust threshold as needed

    # 2. Check Centering (Approximate)
    line_bbox = line_dict.get('bbox', None)
    is_centered_hint = False
    if line_bbox and page_width > 0:
        # --- Centering Thresholds (TUNABLE) ---
        center_tolerance_ratio = 0.15 # How much difference between margins is allowed (relative to page width)
        min_margin_ratio = 0.20     # How much margin must exist on both sides (relative to page width)
        # --- End Tuning ---
        left_margin = line_bbox[0]
        right_margin = page_width - line_bbox[2]
        if abs(left_margin - right_margin) < (page_width * center_tolerance_ratio) and \
           left_margin > (page_width * min_margin_ratio) and \
           right_margin > (page_width * min_margin_ratio):
            is_centered_hint = True

    # 3. Assume break before/after (implicit if it's the only line, checked in main loop)
    # Combine checks
    if is_short and is_centered_hint:
         # Basic check to avoid just numbers or symbols
        if re.search("[a-zA-Z]", line_text):
             return 'chapter', line_text # Assume chapter for simplicity

    return None, None


# --- Main Extraction Function (Using get_text("dict") but simpler logic) ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    doc = None
    extracted_data = []
    current_chapter_title_state = None # Still track the last *detected* title

    try:
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")
        total_pages = len(doc)
        print(f"Total pages in PDF: {total_pages}")

        for page_num_0based, page in enumerate(doc):
            # Page Skipping
            if page_num_0based < start_skip: continue
            if page_num_0based >= total_pages - end_skip: break
            adjusted_page_num = page_num_0based - start_skip + start_page_offset
            page_width = page.rect.width

            try:
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_PRESERVE_LIGATURES)["blocks"] # Using dict

                for b in blocks:
                    if b['type'] == 0: # Text block
                        block_lines = b['lines']
                        # Check if the block contains only one line (potential heading isolation)
                        is_single_line_block = len(block_lines) == 1

                        for l in block_lines:
                            line_dict = l
                            line_text = "".join(s["text"] for s in line_dict["spans"]).strip()

                            if not line_text or is_likely_metadata_or_footer(line_text): continue

                            # --- Check Heading ---
                            # Only check layout if it's the only line in the block
                            heading_type, heading_text = (None, None)
                            if is_single_line_block:
                                heading_type, heading_text = check_heading_by_layout(
                                    line_dict,
                                    page_width
                                    # No need to pass dominant_font_size or current_chapter_title
                                )

                            is_heading = heading_type is not None

                            if heading_type == 'chapter':
                                current_chapter_title_state = heading_text # Update state
                                # Append tuple: (heading_text, page_num, chapter_title, subchapter_title)
                                extracted_data.append((heading_text, adjusted_page_num, heading_text, None))
                            # Note: This simplified version doesn't detect subchapters separately
                            else: # Regular text or heading not detected by simple layout
                                try:
                                    sentences_in_line = nltk.sent_tokenize(line_text)
                                    for sentence in sentences_in_line:
                                        sentence_clean = sentence.strip()
                                        if sentence_clean:
                                            # Append tuple: (text, page_num, None, None)
                                            extracted_data.append((sentence_clean, adjusted_page_num, None, None))
                                except Exception as e_nltk:
                                    st.warning(f"NLTK Error (Page {adjusted_page_num}): Line '{line_text}'. Error: {e_nltk}")
                                    if line_text:
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
