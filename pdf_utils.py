import fitz
import re
import nltk
import statistics
import streamlit as st

# --- NLTK Download Logic ---
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

# --- Font Size Analysis ---
def get_dominant_font_stats(page):
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
    if not sizes:
        return None, None
    try:
        dominant_size = max(sizes, key=sizes.get)
        all_sizes_list = [size for size, count in sizes.items() for _ in range(count)]
        median_size = statistics.median(all_sizes_list) if all_sizes_list else dominant_size
        return dominant_size, median_size
    except Exception as e:
        print(f"Warning: Error calculating dominant font stats: {e}")
        return list(sizes.keys())[0] if sizes else None, None

# --- Metadata/Footer Check ---
def is_likely_metadata_or_footer(line):
    line = line.strip()
    if not line:
        return True
    cleaned_line = re.sub(r"^\W+|\W+$", "", line)
    if cleaned_line.isdigit() and line == cleaned_line and len(cleaned_line) < 4:
        return True
    if "www." in line or ".com" in line or "@" in line or "books" in line.lower() or "global" in line.lower() or ("center" in line.lower() and "peace" in line.lower()):
         if len(line.split()) < 10:
              return True
    if re.match(r"^\s*Page\s+\d+\s*$", line, re.IGNORECASE):
         return True
    if "©" in line or "copyright" in line.lower() or "first published" in line.lower() or "isbn" in line.lower():
         return True
    if "printed in" in line.lower():
         return True
    if "nizamuddin" in line.lower() or "new delhi" in line.lower() or "noida" in line.lower() or "bensalem" in line.lower() or "Byberry Road" in line:
         return True
    if len(set(line.strip())) < 4 and len(line.strip()) > 4:
         return True
    if line.endswith(cleaned_line) and cleaned_line.isdigit() and len(line) < 80 and len(line) > len(cleaned_line) + 2:
         if not re.search(r"[a-zA-Z]{4,}", line):
              return True
    return False

# --- Individual Heading Heuristics ---
def _is_chapter_heading_by_font(line_text, line_spans, dominant_font_size):
    """Checks if the font size of the line indicates a chapter heading."""
    words = line_text.split()
    num_words = len(words)
    if not line_spans:
        return False
    try:
        valid_spans = [s for s in line_spans if s['size'] > 5 and s['text'].strip()]
        if not valid_spans:
            return False
        sizes_in_line = [s["size"] for s in valid_spans]
        max_line_size = round(max(sizes_in_line), 1)
        min_line_size = round(min(sizes_in_line), 1)
        is_consistent_size = (max_line_size - min_line_size) < 1.5
    except Exception:
        return False

    if dominant_font_size and is_consistent_size:
        # Lowered thresholds: require a moderate increase
        font_size_threshold_points = 1.0  # lowered from 1.8
        font_size_threshold_ratio = 1.10  # lowered from 1.18
        if max_line_size >= dominant_font_size + font_size_threshold_points or max_line_size > dominant_font_size * font_size_threshold_ratio:
            if num_words < 9 and not line_text[-1] in ['.', '?', '!', ':', ',', ';'] and re.search("[a-zA-Z]", line_text):
                return True
    return False

def _is_subchapter_heading_by_font(line_text, line_spans, dominant_font_size):
    """Checks if the font size of the line indicates a subchapter heading."""
    words = line_text.split()
    num_words = len(words)
    if not line_spans:
        return False
    try:
        valid_spans = [s for s in line_spans if s['size'] > 5 and s['text'].strip()]
        if not valid_spans:
            return False
        sizes_in_line = [s["size"] for s in valid_spans]
        max_line_size = round(max(sizes_in_line), 1)
        min_line_size = round(min(sizes_in_line), 1)
        is_consistent_size = (max_line_size - min_line_size) < 1.5
    except Exception:
        return False

    if dominant_font_size and is_consistent_size:
        sub_font_threshold_points = 0.5  # lowered from 0.8
        sub_font_threshold_ratio = 1.03  # lowered from 1.05
        if max_line_size >= dominant_font_size + sub_font_threshold_points or max_line_size > dominant_font_size * sub_font_threshold_ratio:
            if num_words < 12 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
                if line_text.istitle() or (sum(1 for c in line_text if c.isupper()) / len(line_text.replace(" ","")) > 0.3):
                    if len(line_text) > 4:
                        return True
    return False

def _is_heading_by_style(line_text, line_spans):
    """Checks for italic/bold styling; returns 'chapter' or 'subchapter' hint if detected."""
    words = line_text.split()
    num_words = len(words)
    try:
        valid_spans = [s for s in line_spans if s['text'].strip()]
        if not valid_spans:
            return None
        flags = valid_spans[0]['flags']
        is_italic = bool(flags & 1)
        is_bold = bool(flags & 4)
        if (is_italic or is_bold) and num_words < 12 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
            if line_text.istitle() and num_words < 8:
                return 'chapter'
            elif len(line_text) > 4:
                return 'subchapter'
    except Exception:
        pass
    return None

def _is_heading_by_case(line_text):
    """Checks the case and length of the line; returns 'subchapter' hint if it meets criteria."""
    words = line_text.split()
    num_words = len(words)
    if (line_text.istitle() or (line_text.isupper() and len(line_text) > 3)) and num_words < 12:
        if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
            if len(line_text) > 4:
                return 'subchapter'
    return None

# --- Consolidated Heading Checker ---
def check_heading_heuristics(line_text, line_spans, dominant_font_size, current_chapter_title):
    """
    Analyzes a line using multiple heuristics to determine if it's a chapter or subchapter.
    Returns:
         ('chapter', heading_text) or ('subchapter', heading_text) if detected,
         or (None, None) if it's regular text.
    """
    line_text = line_text.strip()
    words = line_text.split()
    num_words = len(words)
    if not line_text:
        return None, None
    if is_likely_metadata_or_footer(line_text):
        return None, None  # Skip metadata/footer lines

    # 1. Explicit chapter/section keywords with numbering (High Confidence)
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+[:\.\s]*", line_text, re.IGNORECASE) and num_words < 8:
        return 'chapter', line_text
    if re.match(r"^\s*[IVXLCDM]+\.?\s+.{3,}", line_text) and num_words < 10:
        return 'chapter', line_text
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line_text) and num_words < 8:
        return 'chapter', line_text

    # 2. Font Size Heuristics
    if _is_chapter_heading_by_font(line_text, line_spans, dominant_font_size):
        return 'chapter', line_text
    if current_chapter_title and _is_subchapter_heading_by_font(line_text, line_spans, dominant_font_size):
        return 'subchapter', line_text

    # 3. Style Check (Bold/Italic)
    style_hint = _is_heading_by_style(line_text, line_spans)
    if style_hint == 'chapter':
        return 'chapter', line_text
    elif style_hint == 'subchapter' and current_chapter_title:
        return 'subchapter', line_text

    # 4. Case/Length Heuristic:
    # If the line is in Title Case (or all uppercase) and short:
    # - If no chapter exists, treat it as a chapter
    # - If a chapter exists, treat it as a subchapter.
    case_hint = _is_heading_by_case(line_text)
    if case_hint == 'subchapter':
        if not current_chapter_title:
            return 'chapter', line_text
        else:
            return 'subchapter', line_text

    return None, None

# --- Main Extraction Function ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    """
    Extract text and split it into sentences while tracking pages and detecting headings.
    Returns a list of tuples: (sentence/heading text, page number, chapter heading, subchapter heading).
    """
    doc = None
    extracted_data = []
    current_chapter_title_state = None
    dominant_body_size = 10  # Default fallback
    try:
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")
        total_pages = len(doc)

        # --- Pre-scan to gather global font size info ---
        all_sizes_counts = {}
        for page in doc:
            try:
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
                for b in blocks:
                    if b['type'] == 0:
                        for l in b["lines"]:
                            for s in l["spans"]:
                                text = s["text"].strip()
                                if text and 'size' in s and s['size'] > 5:
                                    size = round(s["size"], 1)
                                    all_sizes_counts[size] = all_sizes_counts.get(size, 0) + len(text)
            except Exception as e:
                print(f"Pre-scan error on a page: {e}")
        if all_sizes_counts:
            dominant_body_size = max(all_sizes_counts, key=all_sizes_counts.get)
            print(f"Determined dominant body font size: {dominant_body_size}")
        else:
            print("Could not determine dominant font size from pre-scan. Using default.")

        # --- Main Page Processing Loop ---
        for page_num_0based, page in enumerate(doc):
            if page_num_0based < start_skip:
                continue
            if page_num_0based >= total_pages - end_skip:
                break
            adjusted_page_num = page_num_0based - start_skip + start_page_offset

            try:
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
                for b in blocks:
                    if b['type'] == 0:
                        for l in b["lines"]:
                            line_spans = l["spans"]
                            line_text = "".join(s["text"] for s in line_spans).strip()
                            if not line_text or is_likely_metadata_or_footer(line_text):
                                continue

                            # --- Use consolidated heading heuristic ---
                            heading_type, heading_text = check_heading_heuristics(
                                line_text,
                                line_spans,
                                dominant_body_size,
                                current_chapter_title_state
                            )

                            if heading_type == 'chapter':
                                current_chapter_title_state = heading_text  # Update the current chapter context
                                extracted_data.append((heading_text, adjusted_page_num, heading_text, None))
                            elif heading_type == 'subchapter':
                                extracted_data.append((heading_text, adjusted_page_num, None, heading_text))
                            else:
                                try:
                                    sentences_in_line = nltk.sent_tokenize(line_text)
                                    for sentence in sentences_in_line:
                                        sentence_clean = sentence.strip()
                                        if sentence_clean:
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
        if doc:
            doc.close()
