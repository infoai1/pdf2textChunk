import fitz
import re
import nltk
import statistics
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


# --- Font Size Analysis ---
def get_dominant_font_stats(page):
    # ... (Keep as is) ...
    sizes = {}
    try:
        blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
        for b in blocks:
            if b['type'] == 0:
                for l in b["lines"]:
                    for s in l["spans"]:
                        text = s["text"].strip()
                        if text and 'size' in s and s['size'] > 5:
                            size = round(s["size"], 1)
                            sizes[size] = sizes.get(size, 0) + len(text)
    except Exception as e:
        print(f"Warning: Error getting font stats: {e}")
        return None, None
    if not sizes: return None, None
    try:
        dominant_size = max(sizes, key=sizes.get)
        return dominant_size, None
    except Exception as e:
        print(f"Warning: Error calculating dominant font stats: {e}")
        return list(sizes.keys())[0] if sizes else None, None

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


# --- Simplified Heading Checker ---
def check_heading_heuristics_simple(line_dict, dominant_font_size, current_chapter_title):
    """
    Simplified heuristic focusing on Italic/Bold flags, Title Case, and Length.
    Returns ('chapter', text), ('subchapter', text), or (None, None).
    Font size check is less emphasized here but can be added back if needed.
    """
    line_text = "".join(s["text"] for s in line_dict["spans"]).strip()
    words = line_text.split()
    num_words = len(words)

    if not line_text or num_words == 0: return None, None
    if is_likely_metadata_or_footer(line_text): return None, None

    # --- Extract Style Flags ---
    is_mostly_italic = False
    is_mostly_bold = False
    total_chars = 0
    italic_chars = 0
    bold_chars = 0

    try:
        valid_spans = [s for s in line_dict["spans"] if s['text'].strip()]
        if not valid_spans: return None, None

        for s in valid_spans:
            span_len = len(s['text'].strip())
            total_chars += span_len
            flags = s.get('flags', 0)
            if flags & 1: italic_chars += span_len # Italic
            if flags & 4: bold_chars += span_len # Bold

        if total_chars > 0:
            is_mostly_italic = (italic_chars / total_chars) > 0.6
            is_mostly_bold = (bold_chars / total_chars) > 0.6

    except Exception as e:
        # print(f"Warning: Could not process flags for line '{line_text}': {e}")
        pass # Continue without style info if flags error out

    # --- Apply Rules ---

    # Rule 1: Explicit Keywords (Highest Priority)
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", line_text, re.IGNORECASE) and num_words < 8:
        return 'chapter', line_text

    # Rule 2: Italic/Bold + Title Case + Short = Likely Chapter
    # This matches the visual style of the examples provided
    if (is_mostly_italic or is_mostly_bold) and line_text.istitle() and 1 < num_words < 10:
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
             return 'chapter', line_text

    # Rule 3: Title Case + Short (No Style) = Maybe Subchapter? (Lower confidence)
    if line_text.istitle() and 1 < num_words < 12:
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
              if current_chapter_title: # Only guess subchapter if we are in a chapter
                   return 'subchapter', line_text
              # else: Might be a chapter title missed above, could return 'chapter' as fallback

    # Rule 4: Numbered List like items - treat as chapter for now
    if re.match(r"^\s*[IVXLCDM]+\.?\s+.{3,}", line_text) and num_words < 10: return 'chapter', line_text
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line_text) and num_words < 8: return 'chapter', line_text


    return None, None # Not detected as heading


# --- Main Extraction Function ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    doc = None
    extracted_data = []
    current_chapter_title_state = None
    dominant_body_size = 10 # Default fallback (less critical now)

    try:
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")
        total_pages = len(doc)

        # Optional: Font Pre-scan (can keep it to print the dominant size for info)
        try:
            all_sizes_counts = {}
            scan_limit = total_pages - end_skip; scan_start = start_skip; max_scan_pages = 15
            for i in range(scan_start, min(scan_limit, scan_start + max_scan_pages)):
                page = doc[i]; blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
                for b in blocks:
                    if b['type'] == 0:
                        for l in b["lines"]:
                            for s in l["spans"]:
                                text = s["text"].strip(); size = round(s.get("size", 0), 1)
                                if text and size > 5: all_sizes_counts[size] = all_sizes_counts.get(size, 0) + len(text)
            if all_sizes_counts: dominant_body_size = max(all_sizes_counts, key=all_sizes_counts.get)
            print(f"--- Dominant body font size (estimated): {dominant_body_size} ---")
        except Exception as e: print(f"--- Font Pre-scan Warning: {e}. Using default {dominant_body_size}. ---")

        # --- Main Page Processing Loop ---
        for page_num_0based, page in enumerate(doc):
            if page_num_0based < start_skip: continue
            if page_num_0based >= total_pages - end_skip: break
            adjusted_page_num = page_num_0based - start_skip + start_page_offset

            try:
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
                for b in blocks:
                    if b['type'] == 0: # Text block
                        for l in b["lines"]:
                            line_dict = l # Pass the whole line dictionary
                            line_text = "".join(s["text"] for s in l["spans"]).strip()

                            if not line_text or is_likely_metadata_or_footer(line_text): continue

                            # --- Use Simplified Heading Checker ---
                            heading_type, heading_text = check_heading_heuristics_simple(
                                line_dict, # Pass the line dictionary
                                dominant_body_size, # Still needed if font rules are used
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
