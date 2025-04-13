import fitz
import re
import nltk
import statistics
import streamlit as st # Now used for error reporting directly in the app

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
            st.error(f"Download Error: Failed to download NLTK '{resource_name}' data: {e}")
            return False
    except Exception as e_find:
        st.error(f"NLTK Find Error: An error occurred checking for NLTK data '{resource_name}': {e_find}")
        return False
    return True

# --- Heuristics (Keep as is from previous version) ---
# (is_likely_chapter_heading_fs, is_likely_subchapter_heading_fs, is_likely_metadata_or_footer)
# --- Font Size Analysis (Keep as is) ---
# (get_dominant_font_stats)
def is_likely_chapter_heading_fs(line_text, line_spans, dominant_font_size):
    """Guess if a line is a chapter heading using font size."""
    line_text = line_text.strip()
    words = line_text.split()
    num_words = len(words)
    if not line_text or num_words > 10: return None
    if not line_spans: return None
    try:
        valid_spans = [s for s in line_spans if s['size'] > 5 and s['text'].strip()]
        if not valid_spans: return None
        sizes_in_line = [s["size"] for s in valid_spans]
        max_line_size = round(max(sizes_in_line), 1)
        min_line_size = round(min(sizes_in_line), 1)
        is_consistent_size = (max_line_size - min_line_size) < 1.5
    except Exception as e: return None
    is_significantly_larger = False
    if dominant_font_size and is_consistent_size:
        font_size_threshold_points = 1.8
        font_size_threshold_ratio = 1.18
        if max_line_size >= dominant_font_size + font_size_threshold_points or max_line_size > dominant_font_size * font_size_threshold_ratio:
            is_significantly_larger = True
    if is_significantly_larger:
        if num_words < 9 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
            if re.search("[a-zA-Z]", line_text): return line_text
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+[:\.\s]*", line_text, re.IGNORECASE): return line_text
    if re.match(r"^\s*[IVXLCDM]+\.?\s+.{3,}", line_text) and num_words < 10: return line_text
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line_text) and num_words < 8: return line_text
    return None

def is_likely_subchapter_heading_fs(line_text, line_spans, dominant_font_size, current_chapter_title):
    """Guess if a line is a subchapter heading using font size."""
    line_text = line_text.strip()
    words = line_text.split()
    num_words = len(words)
    if not line_text or num_words > 15: return None
    if current_chapter_title is None: return None
    if is_likely_metadata_or_footer(line_text): return None
    if is_likely_chapter_heading_fs(line_text, line_spans, dominant_font_size): return None
    if not line_spans: return None
    try:
        valid_spans = [s for s in line_spans if s['size'] > 5 and s['text'].strip()]
        if not valid_spans: return None
        sizes_in_line = [s["size"] for s in valid_spans]
        max_line_size = round(max(sizes_in_line), 1)
        min_line_size = round(min(sizes_in_line), 1)
        is_consistent_size = (max_line_size - min_line_size) < 1.0
    except Exception: return None
    is_larger_than_body = False
    if dominant_font_size and is_consistent_size:
        sub_font_threshold_points = 0.8
        sub_font_threshold_ratio = 1.05
        if max_line_size >= dominant_font_size + sub_font_threshold_points or max_line_size > dominant_font_size * sub_font_threshold_ratio:
             is_larger_than_body = True
    if is_larger_than_body:
        if num_words < 12 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
             if line_text.istitle() or (sum(1 for c in line_text if c.isupper()) / len(line_text.replace(" ","")) > 0.3):
                  if len(line_text) > 4: return line_text
    return None

def is_likely_metadata_or_footer(line):
    """Heuristic to filter metadata/footers."""
    line = line.strip()
    if not line: return True
    cleaned_line = re.sub(r"^\W+|\W+$", "", line)
    if cleaned_line.isdigit() and line == cleaned_line and len(cleaned_line) < 4 : return True
    if "www." in line or ".com" in line or "@" in line or "goodwordbooks" in line or "cpsglobal" in line:
         if len(line.split()) < 10: return True
    if re.match(r"^\s*Page\s+\d+\s*$", line, re.IGNORECASE): return True
    if "©" in line or "copyright" in line.lower() or "first published" in line.lower() or "isbn" in line.lower(): return True
    if "printed in" in line.lower(): return True
    if len(set(line.strip())) < 4 and len(line.strip()) > 4: return True
    if line.endswith(cleaned_line) and cleaned_line.isdigit() and len(line) < 80 and len(line) > len(cleaned_line) + 2:
         if not re.search(r"[a-zA-Z]{4,}", line): return True # TOC Check
    return False

def get_dominant_font_stats(page):
    """Analyzes font sizes on a page."""
    sizes = {}
    try:
        blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
        for b in blocks:
            if b['type'] == 0:
                for l in b["lines"]:
                    for s in l["spans"]:
                        text = s["text"].strip()
                        if text and s['size'] > 5:
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
        return list(sizes.keys())[0] if sizes else None, None


# --- Main Extraction Function (MODIFIED with detailed error checks) ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    doc = None
    extracted_data = []
    current_chapter_title_state = None
    dominant_body_size = None # Initialize outside loop

    try:
        # --- 1. Open PDF ---
        try:
            doc = fitz.open(stream=uploaded_file_content, filetype="pdf")
            total_pages = len(doc)
        except Exception as e:
            st.error(f"Fitz Error: Failed to open PDF. Is it a valid PDF file? Error: {e}")
            return None

        # --- 2. Font Pre-scan ---
        try:
            all_sizes_counts = {}
            scan_limit = total_pages - end_skip
            scan_start = start_skip
            page_scan_count = 0
            max_scan_pages = 15
            for i in range(scan_start, scan_limit):
                if page_scan_count >= max_scan_pages: break
                page = doc[i]
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
            if all_sizes_counts:
                dominant_body_size = max(all_sizes_counts, key=all_sizes_counts.get)
            else:
                st.warning("Could not determine dominant font size from pre-scan.")
        except Exception as e:
            st.warning(f"Font Pre-scan Warning: Could not reliably determine dominant font size. Error: {e}")
            dominant_body_size = 10 # Use a default guess


        # --- 3. Main Page Processing Loop ---
        for page_num_0based, page in enumerate(doc):
            if page_num_0based < start_skip: continue
            if page_num_0based >= total_pages - end_skip: break
            adjusted_page_num = page_num_0based - start_skip + start_page_offset

            try: # Try block for processing a single page
                page_dominant_size = dominant_body_size # Use pre-scanned if available
                if page_dominant_size is None:
                    pds, _ = get_dominant_font_stats(page)
                    page_dominant_size = pds if pds else 10 # Fallback for this page

                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]

                for b in blocks:
                    if b['type'] == 0: # Text block
                        for l in b["lines"]:
                            line_spans = l["spans"]
                            line_text = "".join(s["text"] for s in line_spans).strip()

                            if is_likely_metadata_or_footer(line_text) or not line_text: continue

                            # Check for heading type using the new function
                            heading_type, heading_text = check_heading_heuristics(line_text, line_spans, page_dominant_size)

                            if heading_type == 'chapter':
                                current_chapter_title_state = heading_text
                                extracted_data.append((heading_text, adjusted_page_num, heading_text, None))
                            elif heading_type == 'subchapter':
                                if current_chapter_title_state is not None:
                                    extracted_data.append((heading_text, adjusted_page_num, None, heading_text))
                                else: # Treat as text if no chapter context yet
                                    is_heading = False
                            else: # Regular text
                                is_heading = False

                            if not is_heading:
                                # --- NLTK Tokenization Try Block ---
                                try:
                                    sentences_in_line = nltk.sent_tokenize(line_text)
                                    for sentence in sentences_in_line:
                                        sentence_clean = sentence.strip()
                                        if sentence_clean:
                                            extracted_data.append((sentence_clean, adjusted_page_num, None, None))
                                except Exception as e_nltk:
                                    st.warning(f"NLTK Error (Page {adjusted_page_num}): Failed on line '{line_text}'. Appending raw line. Error: {e_nltk}")
                                    if line_text: extracted_data.append((line_text, adjusted_page_num, None, None))
                                # --- End NLTK Try Block ---

            except Exception as e_page:
                 st.error(f"Processing Error: Failed to process page {adjusted_page_num}. Error: {e_page}")
                 # Optionally continue to next page or stop? For now, continue.
                 continue
        # --- End Main Page Processing Loop ---

        return extracted_data

    except Exception as e_main:
        # Catch any other unexpected error during setup or loop
        st.error(f"Main Extraction Error: An unexpected error occurred: {e_main}")
        return None
    finally:
        if doc: doc.close()
