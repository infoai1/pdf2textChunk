# Enhanced heading detection with better handling for centered italic chapter titles
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
    if not sizes: return None, None
    try:
        dominant_size = max(sizes, key=sizes.get)
        return dominant_size, None
    except Exception as e:
        print(f"Warning: Error calculating dominant font stats: {e}")
        return list(sizes.keys())[0] if sizes else None, None

# --- Metadata/Footer Check ---
def is_likely_metadata_or_footer(line):
    line = line.strip()
    if not line: return True
    cleaned_line = re.sub(r"^\W+|\W+$", "", line)
    if cleaned_line.isdigit() and line == cleaned_line and len(cleaned_line) < 4: return True
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

# --- Heading Detection Heuristic ---
def check_heading_heuristics(line_dict, page_width, dominant_font_size, current_chapter_title):
    line_text = "".join(s["text"] for s in line_dict["spans"]).strip()
    words = line_text.split()
    num_words = len(words)

    if not line_text or num_words == 0: return None, None
    if is_likely_metadata_or_footer(line_text): return None, None

    max_line_size = 0
    min_line_size = 1000
    total_chars = 0
    italic_chars = 0
    bold_chars = 0

    try:
        valid_spans = [s for s in line_dict["spans"] if s['size'] > 5 and s['text'].strip()]
        if not valid_spans: return None, None

        sizes_in_line = [s["size"] for s in valid_spans]
        max_line_size = round(max(sizes_in_line), 1)
        min_line_size = round(min(sizes_in_line), 1)
        is_consistent_size = (max_line_size - min_line_size) < 1.5

        for s in valid_spans:
            span_len = len(s['text'].strip())
            total_chars += span_len
            flags = s.get('flags', 0)
            if flags & 1: italic_chars += span_len
            if flags & 4: bold_chars += span_len

    except Exception:
        return None, None

    italic_ratio = (italic_chars / total_chars) if total_chars > 0 else 0
    bold_ratio = (bold_chars / total_chars) if total_chars > 0 else 0
    is_mostly_italic = italic_ratio > 0.6
    is_mostly_bold = bold_ratio > 0.6

    line_bbox = line_dict.get('bbox', None)
    is_centered = False
    if line_bbox and page_width > 0:
        left_margin = line_bbox[0]
        right_margin = page_width - line_bbox[2]
        if abs(left_margin - right_margin) < (page_width * 0.12) and left_margin > (page_width * 0.1):
            is_centered = True

    is_significantly_larger = dominant_font_size and max_line_size >= dominant_font_size + 1.0

    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", line_text, re.IGNORECASE) and num_words < 8:
        return 'chapter', line_text

    if (is_significantly_larger or is_mostly_italic or is_mostly_bold) and num_words <= 10:
        if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
            if is_significantly_larger or (is_mostly_italic and is_centered) or (is_mostly_bold and is_centered):
                return 'chapter', line_text

    if is_centered and is_mostly_italic and is_consistent_size and abs(max_line_size - dominant_font_size) <= 0.5:
        if 3 <= num_words <= 12:
            return 'chapter', line_text

    heading_keywords = ["Paradise", "Creation Plan", "Life After Death", "Afterworld", "Accountability", "Judged", "God-Oriented"]
    if any(kw.lower() in line_text.lower() for kw in heading_keywords):
        if is_mostly_italic and num_words <= 12:
            return 'chapter', line_text

    if (is_mostly_italic or is_mostly_bold) and 4 <= num_words <= 12 and not line_text.endswith(('.', '?', '!', ':')):
        return ('subchapter', line_text) if current_chapter_title else ('chapter', line_text)

    return None, None
