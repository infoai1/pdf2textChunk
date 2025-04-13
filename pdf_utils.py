import fitz  # PyMuPDF
import re
import nltk
import statistics # To find median/mode font size
import streamlit as st # Keep for st.info/success/error during download only

# --- NLTK Download Logic (Keep as is) ---
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
        blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
        for b in blocks:
            if b['type'] == 0: # Text block
                for l in b["lines"]:
                    for s in l["spans"]:
                        size = round(s["size"]) # Round size to group similar ones
                        sizes[size] = sizes.get(size, 0) + len(s["text"].strip()) # Count characters per size
    except Exception as e:
        print(f"Warning: Error getting font stats from page dict: {e}")
        return None, None # Indicate failure

    if not sizes:
        return None, None

    try:
        # Find the font size with the most characters (likely body text)
        dominant_size = max(sizes, key=sizes.get)
        # Calculate median size for comparison, could be useful later
        all_sizes_list = []
        for size, count in sizes.items():
            all_sizes_list.extend([size] * count) # Weighted list by character count
        median_size = statistics.median(all_sizes_list) if all_sizes_list else dominant_size

        return dominant_size, median_size
    except Exception as e:
         print(f"Warning: Error calculating dominant font stats: {e}")
         return None, None


# --- Revised Heuristics incorporating Font Size ---
# We will now pass dominant_font_size to these functions

def is_likely_chapter_heading_fs(line_text, line_spans, dominant_font_size):
    """Guess if a line is a chapter heading using font size."""
    line_text = line_text.strip()
    if not line_text or len(line_text.split()) > 10: return None

    # Calculate average/max font size for the line
    if not line_spans: return None
    try:
        # Use max font size on the line as representative
        max_line_size = round(max(s["size"] for s in line_spans))
    except ValueError:
        return None # No spans or invalid size data

    # --- Primary Check: Significantly Larger Font ---
    # Heuristic: Chapter heading is at least 1.3x larger (or 2+ points larger) than dominant body text
    if dominant_font_size and max_line_size > dominant_font_size * 1.3 and max_line_size >= dominant_font_size + 2:
         # Secondary checks for confirmation (optional but recommended)
         if len(line_text.split()) < 8 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
              # Check for keywords maybe?
              if re.match(r"^\s*(CHAPTER|SECTION|PART)", line_text, re.IGNORECASE):
                  return line_text # High confidence
              # Check if centered (more complex, needs position info)
              # Check if title case or all caps
              if line_text.istitle() or (line_text.isupper() and len(line_text) > 3):
                   return line_text # Medium confidence
    # Fallback: Check original keyword/case rules if font size check fails or is inconclusive
    # return is_likely_chapter_heading(line_text) # Reuse previous logic as fallback? (optional)

    return None


def is_likely_subchapter_heading_fs(line_text, line_spans, dominant_font_size, current_chapter_title):
    """Guess if a line is a subchapter heading using font size."""
    line_text = line_text.strip()
    if not line_text or len(line_text.split()) > 15: return None
    if current_chapter_title is None: return None
    if is_likely_metadata_or_footer(line_text): return None # Use old metadata check for now
    # Don't identify if it looks like a main chapter heading
    if is_likely_chapter_heading_fs(line_text, line_spans, dominant_font_size): return None

    if not line_spans: return None
    try:
        max_line_size = round(max(s["size"] for s in line_spans))
    except ValueError:
        return None

    # --- Primary Check: Larger (but maybe not *as* large as chapter) Font ---
    # Heuristic: Subchapter slightly larger than body text, but maybe less than chapter
    if dominant_font_size and max_line_size > dominant_font_size * 1.1 and max_line_size >= dominant_font_size + 1:
         # Secondary checks
        if len(line_text.split()) < 12 and not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
             if line_text.istitle() or (sum(1 for c in line_text if c.isupper()) / len(line_text.replace(" ","")) > 0.3):
                   return line_text

    # Fallback to previous case-based logic if font size is same as body? (optional)
    # return is_likely_subchapter_heading(line_text, current_chapter_title)

    return None

# --- Metadata/Footer Check (Keep as is or refine further) ---
def is_likely_metadata_or_footer(line):
    """Basic heuristic to filter out metadata/footers/page numbers."""
    line = line.strip()
    if not line: return True
    cleaned_line = re.sub(r"^\W+|\W+$", "", line)
    if cleaned_line.isdigit() and line == cleaned_line and len(cleaned_line) < 4 : return True # Allow only up to 3 digits
    if "www." in line or ".com" in line or "@" in line or "goodwordbooks" in line or "cpsglobal" in line: return True
    if re.match(r"^\s*Page\s+\d+\s*$", line, re.IGNORECASE): return True
    if "©" in line or "copyright" in line.lower() or "first published" in line.lower() or "isbn" in line.lower(): return True
    if "nizamuddin" in line.lower() or "new delhi" in line.lower() or "noida" in line.lower() or "bensalem" in line.lower(): return True
    if "printed in" in line.lower(): return True
    if len(set(line.strip())) < 4 and len(line.strip()) > 4: return True # Decorative lines
    if line.endswith(cleaned_line) and cleaned_line.isdigit() and len(line) < 80 and len(line) > len(cleaned_line) + 2:
         if not re.search(r"[a-zA-Z]{4,}", line): return True # TOC Check
    # Removed short uppercase filter here, check in heading logic instead
    return False


# --- Main Extraction Function (REVISED TO USE get_text("dict")) ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    """
    Extracts text using block/span info, cleans, splits sentences,
    tracks pages & detects headings based on font size heuristics.
    """
    doc = None
    extracted_data = []
    current_chapter_title_state = None

    try:
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")
        total_pages = len(doc)
        print(f"Total pages in PDF: {total_pages}")

        # --- Optional: Pre-scan for dominant font size across first few content pages ---
        # This can make page-by-page detection more robust if body font is consistent
        dominant_body_size = None
        scanned_sizes = []
        scan_pages = min(10, total_pages - start_skip - end_skip) # Scan up to 10 content pages
        if scan_pages > 0:
             print(f"Pre-scanning first {scan_pages} content pages for dominant font size...")
             for i in range(start_skip, start_skip + scan_pages):
                  if i < total_pages:
                       d_size, _ = get_dominant_font_stats(doc[i])
                       if d_size: scanned_sizes.append(d_size)
             if scanned_sizes:
                  try:
                      dominant_body_size = statistics.mode(scanned_sizes) # Most frequent size
                      print(f"Detected dominant body font size: {dominant_body_size}")
                  except statistics.StatisticsError: # Handle case with no clear mode
                      dominant_body_size = statistics.median(scanned_sizes) if scanned_sizes else None
                      print(f"Using median body font size: {dominant_body_size}")
        # --- End Pre-scan ---


        for page_num_0based, page in enumerate(doc):
            if page_num_0based < start_skip: continue
            if page_num_0based >= total_pages - end_skip: break

            adjusted_page_num = page_num_0based - start_skip + start_page_offset

            # --- Get dominant font size for *this specific page* if pre-scan failed ---
            page_dominant_size = dominant_body_size
            if page_dominant_size is None:
                page_dominant_size, _ = get_dominant_font_stats(page)
                # print(f"Page {adjusted_page_num} dominant size: {page_dominant_size}") # Debug

            try:
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
            except Exception as e:
                print(f"Warning: Failed to get text dict for page {adjusted_page_num}: {e}")
                continue # Skip page if dict fails

            for b in blocks:
                if b['type'] == 0: # Text block
                    for l in b["lines"]:
                        line_text = "".join(s["text"] for s in l["spans"]).strip()
                        line_spans = l["spans"] # Keep span info for font analysis

                        if is_likely_metadata_or_footer(line_text): continue
                        if not line_text: continue

                        chapter_heading = is_likely_chapter_heading_fs(line_text, line_spans, page_dominant_size)
                        subchapter_heading = None if chapter_heading else is_likely_subchapter_heading_fs(line_text, line_spans, page_dominant_size, current_chapter_title_state)
                        is_heading = chapter_heading or subchapter_heading

                        if chapter_heading:
                            current_chapter_title_state = chapter_heading
                            extracted_data.append((chapter_heading, adjusted_page_num, chapter_heading, None))
                            # print(f"CH DETECTED (pg {adjusted_page_num}): {chapter_heading}") # Debug
                        elif subchapter_heading:
                            extracted_data.append((subchapter_heading, adjusted_page_num, None, subchapter_heading))
                            # print(f"SUB DETECTED (pg {adjusted_page_num}): {subchapter_heading}") # Debug
                        else:
                            # Sentence tokenize the line text
                            try:
                                sentences_in_line = nltk.sent_tokenize(line_text)
                                for sentence in sentences_in_line:
                                    sentence_clean = sentence.strip()
                                    if sentence_clean:
                                        extracted_data.append((sentence_clean, adjusted_page_num, None, None))
                            except Exception as e:
                                print(f"Warning: NLTK error on page {adjusted_page_num}, line '{line_text}': {e}")
                                if line_text:
                                    extracted_data.append((line_text, adjusted_page_num, None, None))

        return extracted_data

    except Exception as e:
        print(f"ERROR in extract_sentences_with_structure: {e}")
        return None
    finally:
        if doc: doc.close()
