import fitz
import re
import nltk
import statistics
import streamlit as st

# --- NLTK Download Logic ---
def download_nltk_data(resource_name, resource_path):
    # ... (Keep this function exactly as in the previous version) ...
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
    # ... (Keep this function exactly as in the previous version) ...
    sizes = {}
    try:
        blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
        for b in blocks:
            if b['type'] == 0:
                for l in b["lines"]:
                    for s in l["spans"]:
                        text = s["text"].strip()
                        if text and 'size' in s and s['size'] > 5:
                            # Round to 1 decimal place for slightly more granularity
                            size = round(s["size"], 1)
                            sizes[size] = sizes.get(size, 0) + len(text)
    except Exception as e:
        print(f"Warning: Error getting font stats: {e}")
        return None, None
    if not sizes: return None, None
    try:
        dominant_size = max(sizes, key=sizes.get)
        # For median, maybe use unrounded sizes if available and needed?
        # For simplicity, sticking with rounded dominant size for now.
        return dominant_size, None # Returning only dominant for now
    except Exception as e:
        print(f"Warning: Error calculating dominant font stats: {e}")
        return list(sizes.keys())[0] if sizes else None, None


# --- Metadata/Footer Check ---
def is_likely_metadata_or_footer(line):
    # ... (Keep this function exactly as in the previous version) ...
    line = line.strip()
    if not line: return True
    cleaned_line = re.sub(r"^\W+|\W+$", "", line)
    if cleaned_line.isdigit() and line == cleaned_line and len(cleaned_line) < 4 : return True
    if "www." in line or ".com" in line or "@" in line or "books" in line.lower() or "global" in line.lower() or ("center" in line.lower() and "peace" in line.lower()):
         if len(line.split()) < 10: return True
    if re.match(r"^\s*Page\s+\d+\s*$", line, re.IGNORECASE): return True
    if "©" in line or "copyright" in line.lower() or "first published" in line.lower() or "isbn" in line.lower(): return True
    if "printed in" in line.lower(): return True
    if "nizamuddin" in line.lower() or "new delhi" in line.lower() or "noida" in line.lower() or "bensalem" in line.lower() or "Byberry Road" in line: return True
    if len(set(line.strip())) < 4 and len(line.strip()) > 4: return True
    if line.endswith(cleaned_line) and cleaned_line.isdigit() and len(line) < 80 and len(line) > len(cleaned_line) + 2:
         if not re.search(r"[a-zA-Z]{4,}", line): return True
    return False

def check_heading_heuristics(line_dict, page_width, dominant_font_size, current_chapter_title):
    """
    Analyzes a line dictionary from page.get_text('dict') to determine heading type.
    Returns: ('chapter', heading_text) or ('subchapter', heading_text) or (None, None)
    """
    line_text = "".join(s["text"] for s in line_dict["spans"]).strip()
    words = line_text.split()
    num_words = len(words)

    if not line_text or num_words == 0:
        return None, None
    if is_likely_metadata_or_footer(line_text):
        return None, None

    # --- Line stats ---
    max_line_size = 0
    min_line_size = 1000
    total_chars = 0
    italic_chars = 0
    bold_chars = 0
    font_names = set()

    try:
        valid_spans = [s for s in line_dict["spans"] if s['size'] > 5 and s['text'].strip()]
        if not valid_spans:
            return None, None

        sizes_in_line = [s["size"] for s in valid_spans]
        max_line_size = round(max(sizes_in_line), 1)
        min_line_size = round(min(sizes_in_line), 1)
        is_consistent_size = (max_line_size - min_line_size) < 1.5

        for s in valid_spans:
            span_len = len(s['text'].strip())
            total_chars += span_len
            font_names.add(s['font'])
            flags = s.get('flags', 0)
            if flags & 1:
                italic_chars += span_len
            if flags & 4:
                bold_chars += span_len

    except Exception:
        return None, None

    italic_ratio = (italic_chars / total_chars) if total_chars > 0 else 0
    bold_ratio = (bold_chars / total_chars) if total_chars > 0 else 0
    is_mostly_italic = italic_ratio > 0.6
    is_mostly_bold = bold_ratio > 0.6

    # --- Centering heuristic ---
    line_bbox = line_dict.get('bbox', None)
    is_centered = False
    if line_bbox and page_width > 0:
        line_width = line_bbox[2] - line_bbox[0]
        left_margin = line_bbox[0]
        right_margin = page_width - line_bbox[2]
        if abs(left_margin - right_margin) < (page_width * 0.12) and left_margin > (page_width * 0.1):
            is_centered = True

    # --- Heuristic rules ---
    is_significantly_larger = dominant_font_size and max_line_size >= dominant_font_size + 1.0

    # 1. Explicit chapter identifiers
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", line_text, re.IGNORECASE) and num_words < 8:
        return 'chapter', line_text

    # 2. Large or styled headings
    if (is_significantly_larger or is_mostly_italic or is_mostly_bold) and num_words <= 10:
        if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
            if is_significantly_larger or (is_mostly_italic and is_centered) or (is_mostly_bold and is_centered):
                return 'chapter', line_text

    # 3. NEW: Relaxed condition for centered + italic lines
    if is_centered and is_mostly_italic and is_consistent_size and abs(max_line_size - dominant_font_size) <= 0.5:
        if 3 <= num_words <= 12:
            return 'chapter', line_text

    # 4. Keyword match for titles (optional fallback)
    heading_keywords = ["Paradise", "Creation Plan", "Life After Death", "Afterworld", "Accountability", "Judged", "God-Oriented"]
    if any(kw.lower() in line_text.lower() for kw in heading_keywords):
        if is_mostly_italic and num_words <= 12:
            return 'chapter', line_text

    # 5. Subchapter fallback
    if (is_mostly_italic or is_mostly_bold) and 4 <= num_words <= 12 and not line_text.endswith(('.', '?', '!', ':')):
        if current_chapter_title:
            return 'subchapter', line_text
        else:
            return 'chapter', line_text

    return None, None

    # Calculate style ratios (only if total_chars > 0)
    italic_ratio = (italic_chars / total_chars) if total_chars > 0 else 0
    bold_ratio = (bold_chars / total_chars) if total_chars > 0 else 0
    is_mostly_italic = italic_ratio > 0.7
    is_mostly_bold = bold_ratio > 0.7

    # Basic Centering Check (using bounding box - VERY UNRELIABLE)
    line_bbox = line_dict.get('bbox', None)
    is_centered = False
    if line_bbox and page_width > 0:
        line_width = line_bbox[2] - line_bbox[0]
        left_margin = line_bbox[0]
        right_margin = page_width - line_bbox[2]
        # Check if margins are roughly equal and significant
        if abs(left_margin - right_margin) < (page_width * 0.1) and left_margin > (page_width * 0.15):
            is_centered = True

    # --- DEBUG PRINT ---
    # print(f"\n--- Analyzing Line (Page ?): | BodySz: {dominant_font_size} | MaxLnSz: {max_line_size} | Italic: {is_mostly_italic} | Bold: {is_mostly_bold} | Center: {is_centered} | Words: {num_words} | Text: '{line_text}'")

    # --- Rule Prioritization ---

    # 1. Explicit Chapter Keywords (High Confidence)
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", line_text, re.IGNORECASE) and num_words < 8:
        # print("   DECISION: Chapter (Keyword Match)")
        return 'chapter', line_text

    # 2. Font Size + Style + Case/Length (High Confidence Chapter)
    # Tuned thresholds: Significantly larger OR moderately larger AND italic/bold
    is_significantly_larger = False
    if dominant_font_size and is_consistent_size:
        if max_line_size >= dominant_font_size + 1.5 or max_line_size > dominant_font_size * 1.15:
             is_significantly_larger = True

    if is_significantly_larger or (is_mostly_italic or is_mostly_bold):
        if num_words < 9 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
            # If large font OR (styled AND title case), likely chapter
             if is_significantly_larger or (line_text.istitle() and (is_mostly_italic or is_mostly_bold)):
                # print("   DECISION: Chapter (Font/Style/Case)")
                return 'chapter', line_text

    # 3. Style or Case alone (Medium Confidence - Assume Subchapter if chapter exists)
    if num_words < 12 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
         if (is_mostly_italic or is_mostly_bold or line_text.istitle()):
              if len(line_text) > 4: # Avoid tiny styled snippets
                   if current_chapter_title: # If we are inside a chapter, assume subchapter
                       # print("   DECISION: Subchapter (Style/Case Fallback)")
                       return 'subchapter', line_text
                   else: # If no chapter context, maybe it's an early chapter title?
                        # print("   DECISION: Chapter (Style/Case Fallback - No Context)")
                        return 'chapter', line_text


    # 4. Numbered/Roman List check (if not caught by font/style) - Assume Chapter for now
    if re.match(r"^\s*[IVXLCDM]+\.?\s+.{3,}", line_text) and num_words < 10:
        # print("   DECISION: Chapter (Roman Numeral)")
        return 'chapter', line_text
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line_text) and num_words < 8:
         # print("   DECISION: Chapter (Decimal Numeral)")
         return 'chapter', line_text


    # If none matched, it's regular text
    return None, None

# --- Main Extraction Function ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    """Extracts text, cleans, splits, tracks pages & detects headings using font size."""
    doc = None
    extracted_data = []
    current_chapter_title_state = None
    dominant_body_size = 10 # Default fallback

    try:
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")
        total_pages = len(doc)

        # Font Pre-scan (keep as before)
        try:
            all_sizes_counts = {}
            scan_limit = total_pages - end_skip
            scan_start = start_skip
            page_scan_count = 0
            max_scan_pages = 15
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
                                if text and 'size' in s and s['size'] > 5:
                                    size = round(s["size"], 1) # Use 1 decimal place
                                    all_sizes_counts[size] = all_sizes_counts.get(size, 0) + len(text)
                page_scan_count += 1
            if all_sizes_counts:
                dominant_body_size = max(all_sizes_counts, key=all_sizes_counts.get)
                print(f"--- Determined dominant body font size: {dominant_body_size} ---")
            else: print("--- Could not determine dominant font size from pre-scan. Using default. ---")
        except Exception as e: print(f"--- Font Pre-scan Warning: {e}. Using default. ---")

        # --- Main Page Processing Loop ---
        for page_num_0based, page in enumerate(doc):
            if page_num_0based < start_skip: continue
            if page_num_0based >= total_pages - end_skip: break
            adjusted_page_num = page_num_0based - start_skip + start_page_offset
            page_width = page.rect.width # Get page width for centering check

            try:
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
                for b in blocks:
                    if b['type'] == 0:
                        for l in b["lines"]:
                            line_spans = l["spans"]
                            line_text = "".join(s["text"] for s in line_spans).strip()

                            if not line_text or is_likely_metadata_or_footer(line_text): continue

                            # Use the consolidated heading checker
                            heading_type, heading_text = check_heading_heuristics(
                                l, # Pass the whole line dictionary
                                page_width,
                                dominant_body_size,
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
