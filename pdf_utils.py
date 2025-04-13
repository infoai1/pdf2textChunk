import fitz
import re
import nltk
import statistics
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
def is_likely_metadata_or_footer(line):
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

# --- Simplified Heading Checker with Line Break Context ---
def check_heading_heuristics_simple(
    line_text,
    first_span_font, # Font name from first span (approximate style)
    is_centered_hint, # Boolean hint about centering
    prev_line_ended_break, # Did the previous block end with \n?
    next_line_starts_break, # Does the next block start after a gap?
    current_chapter_title
    ):
    """
    Simplified heuristic focusing on keywords, style hints, case, length, AND line breaks/centering.
    """
    line_text = line_text.strip()
    words = line_text.split()
    num_words = len(words)

    if not line_text or num_words == 0: return None, None
    if is_likely_metadata_or_footer(line_text): return None, None

    is_italic_hint = "italic" in first_span_font.lower()
    is_bold_hint = "bold" in first_span_font.lower()
    is_short_line = num_words < 10
    is_title_case = line_text.istitle()

    # --- Rule Prioritization ---

    # 1. Explicit Chapter Keywords (High Confidence)
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", line_text, re.IGNORECASE) and num_words < 8:
        return 'chapter', line_text

    # 2. Surrounded by Breaks + Centered + Short + Styled/Title Case (Very High Confidence Chapter)
    if prev_line_ended_break and next_line_starts_break and is_centered_hint and is_short_line:
        if is_italic_hint or is_bold_hint or is_title_case:
             # print(f"✅ CH (Breaks+Center+Style/Case): {line_text}")
             return 'chapter', line_text

    # 3. Surrounded by Breaks + Short + Styled/Title Case (High Confidence Chapter)
    if prev_line_ended_break and next_line_starts_break and is_short_line:
        if is_italic_hint or is_bold_hint or is_title_case:
            # print(f"✅ CH (Breaks+Style/Case): {line_text}")
            return 'chapter', line_text

    # 4. Numbered list items (Treat as chapter for now)
    if re.match(r"^\s*[IVXLCDM]+\.?\s+.{3,}", line_text) and num_words < 10: return 'chapter', line_text
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line_text) and num_words < 8: return 'chapter', line_text

    # 5. Other Title Case / Styled lines (Maybe Subchapter?)
    if (is_italic_hint or is_bold_hint or is_title_case) and 1 < num_words < 12:
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
              if current_chapter_title: # Only if inside a chapter
                   # print(f"✅ SUB (Style/Case Fallback): {line_text}")
                   return 'subchapter', line_text
              # else: could be an early chapter missed, but let's be stricter

    return None, None # Default: Not a heading


# --- Main Extraction Function (Using get_text("blocks") for line breaks) ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    doc = None
    extracted_data = []
    current_chapter_title_state = None

    try:
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")
        total_pages = len(doc)

        all_lines_data = [] # Store tuples: (line_text, page_num, first_span_font, line_bbox, page_width)

        # --- Pass 1: Extract all lines with basic info ---
        print("Pass 1: Extracting lines and basic info...")
        for page_num_0based, page in enumerate(doc):
            if page_num_0based < start_skip: continue
            if page_num_0based >= total_pages - end_skip: break
            adjusted_page_num = page_num_0based - start_skip + start_page_offset
            page_width = page.rect.width

            try:
                # Use 'dict' to get detailed span info needed for font style approximation
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
                for b in blocks:
                    if b['type'] == 0: # Text block
                        for l in b["lines"]:
                            line_text = "".join(s["text"] for s in l["spans"]).strip()
                            if not line_text or is_likely_metadata_or_footer(line_text):
                                continue

                            first_span_font = l["spans"][0]['font'] if l["spans"] else "Unknown"
                            line_bbox = l.get('bbox', None)
                            all_lines_data.append((line_text, adjusted_page_num, first_span_font, line_bbox, page_width))

            except Exception as e_page:
                 st.error(f"Extraction Error: Failed during initial text extraction on page {adjusted_page_num}. Error: {e_page}")
                 continue

        # --- Pass 2: Process lines with context (line breaks, centering) ---
        print(f"Pass 2: Analyzing {len(all_lines_data)} extracted lines for structure...")
        for i, (line_text, page_num, first_span_font, line_bbox, page_width) in enumerate(all_lines_data):

             # Check context: Did previous line end with a break? Does next line start after a break?
             # This is approximated by checking if the line is the *first* line in its block
             # A more robust way would involve checking y-coordinates if using get_text("dict") blocks
             # For simplicity with get_text("blocks"), we assume block separation implies breaks.
             # This IS an approximation.
             prev_line_ended_break = (i == 0) or (all_lines_data[i-1][1] != page_num) # Break if previous line was on diff page
             next_line_starts_break = (i == len(all_lines_data) - 1) or (all_lines_data[i+1][1] != page_num) # Break if next line is on diff page
             # TODO: Improve break detection using block info or y-coordinates if needed

             # Basic Centering Check
             is_centered_hint = False
             if line_bbox and page_width > 0:
                 left_margin = line_bbox[0]
                 right_margin = page_width - line_bbox[2]
                 if abs(left_margin - right_margin) < (page_width * 0.15) and left_margin > (page_width * 0.15):
                     is_centered_hint = True

             # --- Check Heading ---
             heading_type, heading_text = check_heading_heuristics_simple(
                 line_text,
                 first_span_font,
                 is_centered_hint,
                 prev_line_ended_break,
                 next_line_starts_break,
                 current_chapter_title_state
             )

             is_heading = heading_type is not None

             if heading_type == 'chapter':
                 current_chapter_title_state = heading_text
                 extracted_data.append((heading_text, adjusted_page_num, heading_text, None))
             elif heading_type == 'subchapter':
                  if current_chapter_title_state: # Ensure we are within a chapter
                     extracted_data.append((heading_text, adjusted_page_num, None, heading_text))
                  else: # Treat as text if no chapter context
                      is_heading = False
             else: # Regular text
                 is_heading = False

             if not is_heading:
                 try:
                     sentences_in_line = nltk.sent_tokenize(line_text)
                     for sentence in sentences_in_line:
                         sentence_clean = sentence.strip()
                         if sentence_clean:
                             extracted_data.append((sentence_clean, adjusted_page_num, None, None))
                 except Exception as e_nltk:
                     st.warning(f"NLTK Error (Page {adjusted_page_num}): Line '{line_text}'. Error: {e_nltk}")
                     if line_text: extracted_data.append((line_text, adjusted_page_num, None, None))


        return extracted_data

    except Exception as e_main:
        st.error(f"Main Extraction Error: An unexpected error occurred: {e_main}")
        st.exception(e_main)
        return None
    finally:
        if doc: doc.close()
