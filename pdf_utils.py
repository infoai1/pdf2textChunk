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
            st.error(f"Failed to download NLTK '{resource_name}' data: {e}")
            return False
    except Exception as e_find:
        st.error(f"An error occurred checking for NLTK data '{resource_name}': {e_find}")
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
            all_sizes_list.extend([size] * count)
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
        is_consistent_size = (max_line_size - min_line_size) < 1.5
    except Exception as e:
        return None

    # --- Primary Check: Font Size ---
    is_significantly_larger = False
    if dominant_font_size and is_consistent_size:
        # --- !! TUNING AREA !! ---
        # Adjust these thresholds based on your PDF analysis
        font_size_threshold_points = 1.8 # How many points bigger? Increased threshold
        font_size_threshold_ratio = 1.18 # How much larger proportionally? Increased threshold
        # --- End Tuning Area ---

        if max_line_size >= dominant_font_size + font_size_threshold_points or max_line_size > dominant_font_size * font_size_threshold_ratio:
            is_significantly_larger = True

    # --- Decision Logic ---
    if is_significantly_larger:
        # If font is larger, apply less strict secondary checks
        if num_words < 9 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
            if re.search("[a-zA-Z]", line_text): # Must contain letters
                # print(f"✅ CH (Font): Size {max_line_size} vs Body {dominant_font_size} | Text: '{line_text}'") # Debug
                return line_text # High confidence based on font size

    # --- Fallback: Keyword/Pattern Check ---
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+[:\.\s]*", line_text, re.IGNORECASE): return line_text
    if re.match(r"^\s*[IVXLCDM]+\.?\s+.{3,}", line_text) and num_words < 10: return line_text
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line_text) and num_words < 8: return line_text

    # Consider case/title check as lower priority if font isn't distinct
    # if (line_text.istitle() or (line_text.isupper() and len(line_text) > 3)) and num_words < 8 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
    #     return line_text

    return None


def is_likely_subchapter_heading_fs(line_text, line_spans, dominant_font_size, current_chapter_title):
    """Guess if a line is a subchapter heading using font size."""
    line_text = line_text.strip()
    words = line_text.split()
    num_words = len(words)

    if not line_text or num_words > 15: return None # Allow slightly longer subheadings
    if current_chapter_title is None: return None
    if is_likely_metadata_or_footer(line_text): return None
    if is_likely_chapter_heading_fs(line_text, line_spans, dominant_font_size): return None # Avoid double ID

    if not line_spans: return None
    try:
        valid_spans = [s for s in line_spans if s['size'] > 5 and s['text'].strip()]
        if not valid_spans: return None
        sizes_in_line = [s["size"] for s in valid_spans]
        max_line_size = round(max(sizes_in_line), 1)
        min_line_size = round(min(sizes_in_line), 1)
        is_consistent_size = (max_line_size - min_line_size) < 1.0
    except Exception:
        return None

    # --- Primary Check: Font Size (Slightly larger than body, less than chapter) ---
    is_larger_than_body = False
    if dominant_font_size and is_consistent_size:
        # --- !! TUNING AREA !! ---
        sub_font_threshold_points = 0.8 # Must be at least slightly bigger
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

    # Optional Fallback to case-based if needed
    # if (line_text.istitle() or ...) and ... : return line_text

    return None


def is_likely_metadata_or_footer(line):
    """Heuristic to filter metadata/footers."""
    line = line.strip()
    if not line: return True
    cleaned_line = re.sub(r"^\W+|\W+$", "", line)
    if cleaned_line.isdigit() and line == cleaned_line and len(cleaned_line) < 4 : return True
    # More aggressive filtering of potential publisher/contact info
    if "www." in line or ".com" in line or "@" in line or "book" in line.lower() or "global" in line.lower() or "center" in line.lower() or "centre" in line.lower():
         if len(line.split()) < 10: # Apply only to shorter lines
              return True
    if re.match(r"^\s*Page\s+\d+\s*$", line, re.IGNORECASE): return True
    if "©" in line or "copyright" in line.lower() or "first published" in line.lower() or "isbn" in line.lower(): return True
    if "printed in" in line.lower(): return True
    if len(set(line.strip())) < 4 and len(line.strip()) > 4: return True # Decorative lines
    if line.endswith(cleaned_line) and cleaned_line.isdigit() and len(line) < 80 and len(line) > len(cleaned_line) + 2:
         if not re.search(r"[a-zA-Z]{4,}", line): return True # TOC Check
    return False

# --- Main Extraction Function ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    """Extracts text, cleans, splits, tracks pages & detects headings using font size."""
    doc = None
    extracted_data = []
    current_chapter_title_state = None

    try:
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")
        total_pages = len(doc)
        print(f"Total pages in PDF: {total_pages}")

        # --- Determine Dominant Font Size (Pre-scan improved) ---
        dominant_body_size = None
        all_sizes_counts = {}
        scan_limit = total_pages - end_skip
        scan_start = start_skip
        page_scan_count = 0
        max_scan_pages = 15 # Scan up to 15 content pages

        print(f"Scanning pages from {scan_start+1} up to {scan_limit} for font stats (max {max_scan_pages})...")
        for i in range(scan_start, scan_limit):
            if page_scan_count >= max_scan_pages: break
            page = doc[i]
            try:
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
                for b in blocks:
                    if b['type'] == 0: # Text block
                        for l in b["lines"]:
                             # Skip lines likely metadata before counting font
                            line_text_for_meta_check = "".join(s["text"] for s in l["spans"]).strip()
                            if is_likely_metadata_or_footer(line_text_for_meta_check): continue

                            for s in l["spans"]:
                                text = s["text"].strip()
                                if text and s['size'] > 5: # Ignore tiny font sizes
                                    size = round(s["size"])
                                    all_sizes_counts[size] = all_sizes_counts.get(size, 0) + len(text)
                page_scan_count += 1
            except Exception as e:
                print(f"Warning: Could not get font stats from page {i+1}: {e}")

        if all_sizes_counts:
            try:
                dominant_body_size = max(all_sizes_counts, key=all_sizes_counts.get)
                print(f"Determined dominant body font size: {dominant_body_size}")
            except Exception as e:
                print(f"Warning: Could not determine dominant font size from scan: {e}")
        else:
             print("Warning: Could not gather any font size data from initial scan.")
        # --- End Pre-scan ---

        # --- Main Page Processing Loop ---
        for page_num_0based, page in enumerate(doc):
            if page_num_0based < start_skip: continue
            if page_num_0based >= total_pages - end_skip: break

            adjusted_page_num = page_num_0based - start_skip + start_page_offset
            page_dominant_size = dominant_body_size # Use pre-scanned size if available

            try:
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
            except Exception as e:
                print(f"Warning: Failed to get text dict for page {adjusted_page_num}: {e}")
                continue

            for b in blocks:
                if b['type'] == 0: # Text block
                    for l in b["lines"]:
                        line_spans = l["spans"]
                        line_text = "".join(s["text"] for s in line_spans).strip()

                        if is_likely_metadata_or_footer(line_text) or not line_text:
                            continue

                        # Use page-specific dominant font only if global one wasn't found
                        current_page_dom_size = page_dominant_size
                        if current_page_dom_size is None:
                             pds, _ = get_dominant_font_stats(page) # Less reliable page-by-page
                             current_page_dom_size = pds if pds else 10 # Default if still unknown

                        chapter_heading = is_likely_chapter_heading_fs(line_text, line_spans, current_page_dom_size)
                        subchapter_heading = None if chapter_heading else is_likely_subchapter_heading_fs(line_text, line_spans, current_page_dom_size, current_chapter_title_state)
                        is_heading = chapter_heading or subchapter_heading

                        if chapter_heading:
                            current_chapter_title_state = chapter_heading
                            extracted_data.append((chapter_heading, adjusted_page_num, chapter_heading, None))
                        elif subchapter_heading:
                            # Subchapter heading IS included as text for chunking
                            extracted_data.append((subchapter_heading, adjusted_page_num, None, subchapter_heading))
                        else:
                            # Sentence tokenize non-heading lines
                            try:
                                sentences_in_line = nltk.sent_tokenize(line_text)
                                for sentence in sentences_in_line:
                                    sentence_clean = sentence.strip()
                                    if sentence_clean:
                                        extracted_data.append((sentence_clean, adjusted_page_num, None, None))
                            except Exception as e:
                                print(f"Warning: NLTK error on page {adjusted_page_num}, line '{line_text}': {e}")
                                if line_text: # Append raw line as fallback
                                    extracted_data.append((line_text, adjusted_page_num, None, None))

        return extracted_data

    except Exception as e:
        print(f"ERROR in extract_sentences_with_structure: {e}")
        return None
    finally:
        if doc: doc.close()
