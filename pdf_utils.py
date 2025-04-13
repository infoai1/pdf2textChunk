import fitz
import re
import nltk
import statistics
import streamlit as st

# --- NLTK Download Logic (Keep as is) ---
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
            st.error(f"Failed to download NLTK '{resource_name}' data: {e}")
            return False
    except Exception as e_find:
        st.error(f"An error occurred checking for NLTK data '{resource_name}': {e_find}")
        return False
    return True

# --- Font Size Analysis (Keep as is) ---
def get_dominant_font_stats(page):
    sizes = {}
    try:
        blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
        for b in blocks:
            if b['type'] == 0:
                for l in b["lines"]:
                    for s in l["spans"]:
                        text = s["text"].strip()
                        if text and s['size'] > 5: # Ignore very small sizes
                            size = round(s["size"])
                            sizes[size] = sizes.get(size, 0) + len(text)
    except Exception as e:
        print(f"Warning: Error getting font stats: {e}")
        return None, None
    if not sizes: return None, None
    try:
        dominant_size = max(sizes, key=sizes.get)
        all_sizes_list = [size for size, count in sizes.items() for _ in range(count)]
        median_size = statistics.median(all_sizes_list) if all_sizes_list else dominant_size
        return dominant_size, median_size
    except Exception as e:
        print(f"Warning: Error calculating dominant font stats: {e}")
        return list(sizes.keys())[0], list(sizes.keys())[0] if sizes else (None, None)

# --- Metadata/Footer Check (Keep as is) ---
def is_likely_metadata_or_footer(line):
    line = line.strip()
    if not line: return True
    cleaned_line = re.sub(r"^\W+|\W+$", "", line)
    if cleaned_line.isdigit() and line == cleaned_line and len(cleaned_line) < 4 : return True
    if "www." in line or ".com" in line or "@" in line or "goodwordbooks" in line or "cpsglobal" in line: return True
    if re.match(r"^\s*Page\s+\d+\s*$", line, re.IGNORECASE): return True
    if "©" in line or "copyright" in line.lower() or "first published" in line.lower() or "isbn" in line.lower(): return True
    if "printed in" in line.lower(): return True
    if len(set(line.strip())) < 4 and len(line.strip()) > 4: return True
    if line.endswith(cleaned_line) and cleaned_line.isdigit() and len(line) < 80 and len(line) > len(cleaned_line) + 2:
         if not re.search(r"[a-zA-Z]{4,}", line): return True
    return False

# --- Heading Detection - REVISED ---
def check_heading_heuristics(line_text, line_spans, dominant_font_size):
    """
    Analyzes a line to determine if it's a chapter, subchapter, or regular text.
    Returns:
        ('chapter', heading_text)
        ('subchapter', heading_text)
        (None, None) -> Not a detected heading
    """
    line_text = line_text.strip()
    words = line_text.split()
    num_words = len(words)

    if not line_text or not line_spans: return None, None

    # --- Calculate Font Properties ---
    max_line_size = 0
    min_line_size = 1000
    is_italic = False
    is_bold = False
    font_name = ""
    text_length = 0
    consistent_size = True

    try:
        valid_spans = [s for s in line_spans if s['size'] > 5 and s['text'].strip()]
        if not valid_spans: return None, None

        sizes_in_line = [s["size"] for s in valid_spans]
        max_line_size = round(max(sizes_in_line), 1)
        min_line_size = round(min(sizes_in_line), 1)
        consistent_size = (max_line_size - min_line_size) < 1.5 # Allow slightly more variance
        text_length = len(line_text)

        # Check flags for bold/italic (common flags: 1=italic, 4=bold)
        # Note: Flags can vary, might need inspection (span['flags'])
        flags = valid_spans[0]['flags'] # Check first span's flags
        is_italic = bool(flags & 1)
        is_bold = bool(flags & 4)
        font_name = valid_spans[0]['font']

    except Exception as e:
        print(f"Debug: Error processing spans for '{line_text}': {e}")
        return None, None # Error processing spans

    # --- DEBUG PRINT ---
    print(f"-> Analyzing Line (Page ?): | BodySz: {dominant_font_size} | MaxLnSz: {max_line_size} | Italic: {is_italic} | Bold: {is_bold} | Words: {num_words} | Text: '{line_text}'")

    # --- Rule Prioritization ---

    # **1. Chapter Keywords (High Confidence)**
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", line_text, re.IGNORECASE) and num_words < 8:
        print("   DECISION: Chapter (Keyword Match)")
        return 'chapter', line_text

    # **2. Font Size Difference (Primary Heuristic for Chapters)**
    is_significantly_larger = False
    if dominant_font_size and consistent_size:
        # --- TUNING AREA ---
        font_size_threshold_points = 1.5 # Lowered
        font_size_threshold_ratio = 1.15 # Lowered
        # --- End Tuning ---
        if max_line_size >= dominant_font_size + font_size_threshold_points or max_line_size > dominant_font_size * font_size_threshold_ratio:
            is_significantly_larger = True

    if is_significantly_larger:
        # Secondary checks for larger font lines -> Likely Chapter
        if num_words < 9 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
            if re.search("[a-zA-Z]", line_text):
                print("   DECISION: Chapter (Font Size Match)")
                return 'chapter', line_text

    # **3. Italic/Bold Style (Good Indicator, maybe Chapter or Subchapter)**
    # If font size *wasn't* the main trigger, check style for shorter lines
    if (is_italic or is_bold) and not is_significantly_larger:
         if num_words < 12 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
              # Could be Chapter or Subchapter - let's assume Subchapter for now if not very large font
              # Or, if it's title case AND italic/bold, maybe lean towards Chapter?
              if line_text.istitle() and num_words < 8:
                   print("   DECISION: Chapter (Style & Title Case)")
                   return 'chapter', line_text
              else:
                   print("   DECISION: Subchapter (Style Match)")
                   return 'subchapter', line_text

    # **4. Case & Length (Lower Confidence - maybe Subchapter?)**
    if (line_text.istitle() or (line_text.isupper() and text_length > 3)) and num_words < 12:
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
              print("   DECISION: Subchapter (Case/Length Match)")
              return 'subchapter', line_text

    # If none of the above, it's regular text
    # print("   DECISION: Text")
    return None, None


# --- Main Extraction Function (Updated to use new checker) ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    """Extracts text, cleans, splits sentences, tracks pages & detects headings using font size."""
    doc = None
    extracted_data = []
    current_chapter_title_state = None

    try:
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")
        total_pages = len(doc)
        print(f"Total pages in PDF: {total_pages}")

        # Determine Dominant Font Size (Pre-scan) - Keep this part
        dominant_body_size = None
        all_sizes_counts = {}
        scan_limit = total_pages - end_skip
        scan_start = start_skip
        page_scan_count = 0
        max_scan_pages = 15

        print(f"Scanning pages from {scan_start+1} up to {scan_limit} for font stats (max {max_scan_pages})...")
        for i in range(scan_start, scan_limit):
            if page_scan_count >= max_scan_pages: break
            page = doc[i]
            try:
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
                for b in blocks:
                    if b['type'] == 0:
                        for l in b["lines"]:
                            line_text_for_meta_check = "".join(s["text"] for s in l["spans"]).strip()
                            if is_likely_metadata_or_footer(line_text_for_meta_check): continue
                            for s in l["spans"]:
                                text = s["text"].strip()
                                if text and s['size'] > 5:
                                    size = round(s["size"])
                                    all_sizes_counts[size] = all_sizes_counts.get(size, 0) + len(text)
                page_scan_count += 1
            except Exception as e: print(f"Warning: Could not get font stats from page {i+1}: {e}")

        if all_sizes_counts:
            try:
                dominant_body_size = max(all_sizes_counts, key=all_sizes_counts.get)
                print(f"Determined dominant body font size: {dominant_body_size}")
            except Exception as e: print(f"Warning: Could not determine dominant font size from scan: {e}")
        else: print("Warning: Could not gather any font size data from initial scan.")
        # Use a default guess if scan fails
        if dominant_body_size is None: dominant_body_size = 10
        # ----- End Pre-scan -----

        # --- Main Page Processing Loop ---
        for page_num_0based, page in enumerate(doc):
            if page_num_0based < start_skip: continue
            if page_num_0based >= total_pages - end_skip: break
            adjusted_page_num = page_num_0based - start_skip + start_page_offset

            try:
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
            except Exception as e: print(f"Warning: Failed get dict page {adjusted_page_num}: {e}"); continue

            for b in blocks:
                if b['type'] == 0: # Text block
                    for l in b["lines"]:
                        line_spans = l["spans"]
                        line_text = "".join(s["text"] for s in line_spans).strip()

                        if is_likely_metadata_or_footer(line_text) or not line_text: continue

                        # Check for heading type using the new function
                        heading_type, heading_text = check_heading_heuristics(line_text, line_spans, dominant_body_size)

                        if heading_type == 'chapter':
                            current_chapter_title_state = heading_text
                            extracted_data.append((heading_text, adjusted_page_num, heading_text, None)) # Chapter tuple
                        elif heading_type == 'subchapter':
                            # Ensure we only assign subchapters if we're 'inside' a chapter
                            if current_chapter_title_state is not None:
                                extracted_data.append((heading_text, adjusted_page_num, None, heading_text)) # Subchapter tuple
                            else: # Treat as normal text if no chapter context yet
                                is_heading = False # Treat as text
                        else: # Regular text
                             is_heading = False

                        # If not a heading, process as regular text sentences
                        if not is_heading:
                            try:
                                sentences_in_line = nltk.sent_tokenize(line_text)
                                for sentence in sentences_in_line:
                                    sentence_clean = sentence.strip()
                                    if sentence_clean:
                                        extracted_data.append((sentence_clean, adjusted_page_num, None, None)) # Text tuple
                            except Exception as e:
                                print(f"Warning: NLTK error page {adjusted_page_num}, line '{line_text}': {e}")
                                if line_text: extracted_data.append((line_text, adjusted_page_num, None, None))

        return extracted_data

    except Exception as e:
        print(f"ERROR in extract_sentences_with_structure: {e}")
        return None
    finally:
        if doc: doc.close()
