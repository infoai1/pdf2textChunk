import fitz  # PyMuPDF
import re
import nltk
import statistics # To find median/mode font size
import streamlit as st # Keep for st.info/success/error during download only

# --- NLTK Download Logic ---
def download_nltk_data(resource_name, resource_path):
    """Helper to download NLTK data if needed. Called from app.py."""
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
    """Analyzes font sizes on a page to find dominant body text size."""
    sizes = {}
    try:
        # Extract text dictionary with detailed span info
        blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
        for b in blocks:
            if b['type'] == 0: # Text block
                for l in b["lines"]:
                    for s in l["spans"]:
                        text = s["text"].strip()
                        if text: # Only consider spans with actual text
                            size = round(s["size"]) # Round size
                            sizes[size] = sizes.get(size, 0) + len(text) # Weight by character count
    except Exception as e:
        print(f"Warning: Error getting font stats from page dict: {e}")
        return None, None

    if not sizes:
        return None, None

    try:
        dominant_size = max(sizes, key=sizes.get)
        all_sizes_list = []
        for size, count in sizes.items():
            all_sizes_list.extend([size] * count) # Weighted list by character count
        median_size = statistics.median(all_sizes_list) if all_sizes_list else dominant_size
        return dominant_size, median_size
    except Exception as e:
         print(f"Warning: Error calculating dominant font stats: {e}")
         # Fallback if max or median fails
         if sizes:
             return list(sizes.keys())[0], list(sizes.keys())[0] # Just return first found size
         return None, None


# --- Heuristics using Font Size (NEEDS TUNING) ---
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
        # Check if font size is consistent across the line (helps avoid mixed-size lines)
        is_consistent_size = (max_line_size - min_line_size) < 1.5 # Allow slightly more variance
    except Exception as e:
        return None # Error processing spans

    # --- Primary Check: Font Size ---
    is_significantly_larger = False
    if dominant_font_size and is_consistent_size:
        # --- !! TUNING AREA !! ---
        # Adjust these thresholds based on your PDF analysis from debug prints
        font_size_threshold_points = 1.8 # How many points bigger?
        font_size_threshold_ratio = 1.18 # How much larger proportionally?
        # --- End Tuning Area ---

        if max_line_size >= dominant_font_size + font_size_threshold_points or max_line_size > dominant_font_size * font_size_threshold_ratio:
            is_significantly_larger = True

    # --- Decision Logic ---
    if is_significantly_larger:
        # If font is larger, apply *less strict* secondary checks
        if num_words < 9 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
            if re.search("[a-zA-Z]", line_text): # Must contain letters
                # print(f"✅ CH (Font): Size {max_line_size} vs Body {dominant_font_size} | Text: '{line_text}'") # Debug
                return line_text # High confidence based on font size

    # --- Fallback: Keyword/Pattern Check ---
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+[:\.\s]*", line_text, re.IGNORECASE):
        # print(f"✅ CH (Keyword): Text: '{line_text}'") # Debug
        return line_text
    if re.match(r"^\s*[IVXLCDM]+\.?\s+.{3,}", line_text) and num_words < 10:
        # print(f"✅ CH (Roman): Text: '{line_text}'") # Debug
        return line_text
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line_text) and num_words < 8:
        # print(f"✅ CH (Number): Text: '{line_text}'") # Debug
        return line_text

    # --- Fallback: Style Check (Italic/Bold might indicate heading) ---
    try:
        if valid_spans:
             flags = valid_spans[0]['flags']
             is_italic = bool(flags & 1)
             is_bold = bool(flags & 4)
             if (is_italic or is_bold) and num_words < 9 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
                  if line_text.istitle(): # If styled AND title case, maybe chapter
                       # print(f"✅ CH (Style+Case): Text: '{line_text}'") # Debug
                       return line_text
    except Exception: pass # Ignore errors getting flags

    return None


def is_likely_subchapter_heading_fs(line_text, line_spans, dominant_font_size, current_chapter_title):
    """Guess if a line is a subchapter heading using font size."""
    line_text = line_text.strip()
    words = line_text.split()
    num_words = len(words)

    if not line_text or num_words > 15: return None
    if current_chapter_title is None: return None # Cannot have subchapter without chapter context
    if is_likely_metadata_or_footer(line_text): return None

    if not line_spans: return None
    try:
        valid_spans = [s for s in line_spans if s['size'] > 5 and s['text'].strip()]
        if not valid_spans: return None
        sizes_in_line = [s["size"] for s in valid_spans]
        max_line_size = round(max(sizes_in_line), 1)
        min_line_size = round(min(sizes_in_line), 1)
        is_consistent_size = (max_line_size - min_line_size) < 1.5
    except Exception:
        return None

    # Avoid identifying it if it passed the *chapter* heading check based on font
    if is_likely_chapter_heading_fs(line_text, line_spans, dominant_font_size):
         return None

    # --- Primary Check: Font Size (Slightly larger than body) ---
    is_larger_than_body = False
    if dominant_font_size and is_consistent_size:
        # --- !! TUNING AREA !! ---
        sub_font_threshold_points = 0.8
        sub_font_threshold_ratio = 1.05
        # --- End Tuning Area ---
        if max_line_size >= dominant_font_size + sub_font_threshold_points or max_line_size > dominant_font_size * sub_font_threshold_ratio:
             is_larger_than_body = True

    # --- Decision Logic ---
    if is_larger_than_body:
        # Apply secondary checks (e.g., title case, no punctuation)
        if num_words < 12 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
             if line_text.istitle() or (sum(1 for c in line_text if c.isupper()) / len(line_text.replace(" ","")) > 0.3):
                  if len(line_text) > 4: # Basic length check
                     # print(f"✅ SUB (Font): Size {max_line_size} vs Body {dominant_font_size} | Text: '{line_text}'") # Debug
                     return line_text

    # --- Fallback: Style Check (maybe italic/bold without size increase means subchapter?) ---
    try:
         if valid_spans:
             flags = valid_spans[0]['flags']
             is_italic = bool(flags & 1)
             is_bold = bool(flags & 4)
             if (is_italic or is_bold) and num_words < 12 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
                  # print(f"✅ SUB (Style): Text: '{line_text}'") # Debug
                  return line_text
    except Exception: pass

    # --- Fallback: Case check if font/style didn't trigger ---
    if (line_text.istitle()) and num_words < 12 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
         if len(line_text) > 4:
             # print(f"✅ SUB (Case): Text: '{line_text}'") # Debug
             return line_text


    return None


def is_likely_metadata_or_footer(line):
    """Heuristic to filter metadata/footers."""
    line = line.strip()
    if not line: return True
    cleaned_line = re.sub(r"^\W+|\W+$", "", line)
    # Check if the cleaned line is *only* a digit and short - more robust for page numbers
    if cleaned_line.isdigit() and line == cleaned_line and len(cleaned_line) < 4 :
        return True
    # Common contact/publishing info (made slightly more general)
    if "www." in line or ".com" in line or "@" in line or "books" in line.lower() or "global" in line.lower() or ("center" in line.lower() and "peace" in line.lower()):
         if len(line.split()) < 10: # Apply only to shorter lines
              return True
    if re.match(r"^\s*Page\s+\d+\s*$", line, re.IGNORECASE): return True
    if "©" in line or "copyright" in line.lower() or "first published" in line.lower() or "isbn" in line.lower(): return True
    if "printed in" in line.lower(): return True
    if "nizamuddin" in line.lower() or "new delhi" in line.lower() or "noida" in line.lower() or "bensalem" in line.lower() or "Byberry Road" in line: return True # Specific addresses
    if len(set(line.strip())) < 4 and len(line.strip()) > 4: return True # Decorative lines
    # Basic TOC check
    if line.endswith(cleaned_line) and cleaned_line.isdigit() and len(line) < 80 and len(line) > len(cleaned_line) + 2:
         if not re.search(r"[a-zA-Z]{4,}", line): return True
    return False


# --- Main Extraction Function ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    """
    Extracts text using block/span info, cleans, splits sentences,
    tracks pages & detects headings based on font size heuristics.
    """
    doc = None
    extracted_data = []
    current_chapter_title_state = None
    dominant_body_size = None # Initialize

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
            max_scan_pages = 15 # Scan up to 15 content pages
            print(f"Scanning pages from {scan_start+1} up to {min(scan_limit, scan_start + max_scan_pages)} for font stats...")
            for i in range(scan_start, min(scan_limit, scan_start + max_scan_pages)):
                page = doc[i]
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
                for b in blocks:
                    if b['type'] == 0:
                        for l in b["lines"]:
                            line_text_for_meta_check = "".join(s["text"] for s in l["spans"]).strip()
                            if is_likely_metadata_or_footer(line_text_for_meta_check): continue
                            for s in l["spans"]:
                                text = s["text"].strip()
                                if text and 'size' in s and s['size'] > 5: # Ensure size key exists
                                    size = round(s["size"])
                                    all_sizes_counts[size] = all_sizes_counts.get(size, 0) + len(text)
                page_scan_count += 1
            if all_sizes_counts:
                dominant_body_size = max(all_sizes_counts, key=all_sizes_counts.get)
                print(f"--- Determined dominant body font size: {dominant_body_size} ---") # DEBUG
            else:
                print("--- Could not determine dominant font size from pre-scan. Using default. ---") # DEBUG
                dominant_body_size = 10 # Default guess
        except Exception as e:
            print(f"--- Font Pre-scan Warning: {e}. Using default. ---") # DEBUG
            dominant_body_size = 10 # Default guess

        # --- 3. Main Page Processing Loop ---
        for page_num_0based, page in enumerate(doc):
            if page_num_0based < start_skip: continue
            if page_num_0based >= total_pages - end_skip: break
            adjusted_page_num = page_num_0based - start_skip + start_page_offset

            try: # Try block for processing a single page
                page_dominant_size_actual = dominant_body_size # Use pre-scanned by default

                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE)["blocks"] # Add flags

                for b in blocks:
                    if b['type'] == 0: # Text block
                        for l in b["lines"]:
                            line_spans = l["spans"]
                            line_text = "".join(s["text"] for s in line_spans).strip()

                            if is_likely_metadata_or_footer(line_text) or not line_text: continue

                            # --- Detailed Debug Print ---
                            print(f"\n--- Analyzing Page {adjusted_page_num} ---")
                            print(f"Line Text: '{line_text}'")
                            print(f"Dominant Font Size (Global): {dominant_body_size}")
                            try:
                                sizes = [round(s['size'],1) for s in line_spans if s['text'].strip() and 'size' in s]
                                flags = [s['flags'] for s in line_spans if s['text'].strip() and 'flags' in s]
                                fonts = [s['font'] for s in line_spans if s['text'].strip() and 'font' in s]
                                print(f"Span Sizes: {sizes}")
                                print(f"Span Flags: {flags}")
                                print(f"Span Fonts: {fonts}")
                            except Exception as span_e:
                                print(f"Could not extract detailed span info: {span_e}")
                            # --- End Detailed Debug Print ---


                            heading_type, heading_text = check_heading_heuristics(line_text, line_spans, page_dominant_size_actual) # Use the determined dominant size

                            is_heading = heading_type is not None # Simplified heading check

                            if heading_type == 'chapter':
                                current_chapter_title_state = heading_text
                                extracted_data.append((heading_text, adjusted_page_num, heading_text, None)) # Chapter tuple
                            elif heading_type == 'subchapter':
                                if current_chapter_title_state is not None:
                                    extracted_data.append((heading_text, adjusted_page_num, None, heading_text)) # Subchapter tuple
                                else: # Treat as text if no chapter context yet
                                    is_heading = False
                            else: # Regular text
                                is_heading = False

                            # If not a heading, process as regular text sentences
                            if not is_heading:
                                try:
                                    sentences_in_line = nltk.sent_tokenize(line_text)
                                    for sentence in sentences_in_line:
                                        sentence_clean = sentence.strip()
                                        # Further clean potentially split words by hyphen across lines if needed (complex)
                                        if sentence_clean:
                                            extracted_data.append((sentence_clean, adjusted_page_num, None, None)) # Text tuple
                                except Exception as e_nltk:
                                    st.warning(f"NLTK Error (Page {adjusted_page_num}): Failed on line '{line_text}'. Appending raw line. Error: {e_nltk}")
                                    if line_text: # Append raw line as fallback
                                        extracted_data.append((line_text, adjusted_page_num, None, None))

            except Exception as e_page:
                 st.error(f"Processing Error: Failed to process page {adjusted_page_num}. Error: {e_page}")
                 continue # Continue to next page
        # --- End Main Page Processing Loop ---

        return extracted_data

    except Exception as e_main:
        st.error(f"Main Extraction Error: An unexpected error occurred: {e_main}")
        st.exception(e_main) # Show traceback in Streamlit
        return None
    finally:
        if doc: doc.close()
