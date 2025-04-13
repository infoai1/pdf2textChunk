import fitz  # PyMuPDF
import re
import nltk
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

# --- Heuristics (Keep as is from previous version, but remember tuning might still be needed) ---
def is_likely_chapter_heading(line):
    """Guess if a line is a chapter heading. Returns the heading text or None."""
    line = line.strip()
    if not line or len(line) > 100: return None # Skip empty or long lines
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+[:\.\s]*", line, re.IGNORECASE): return line.strip()
    if re.match(r"^\s*[IVXLCDM]+\.?\s+.{3,}", line) and len(line.split()) < 10 : return line.strip() # Roman numeral check
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line) and len(line.split()) < 8: return line.strip() # Numbered heading
    words = line.split()
    if 1 < len(words) < 8:
        is_title_case = line.istitle()
        is_all_caps = line.isupper() and len(line) > 3
        has_no_end_punctuation = not line[-1] in ['.', '?', '!', ':', ',', ';']
        if (is_title_case or is_all_caps) and has_no_end_punctuation:
             if not (line[0].islower() and len(words)>1):
                  return line.strip()
    return None

def is_likely_subchapter_heading(line, current_chapter_title):
    """Guess if a line is a subchapter heading."""
    line = line.strip()
    if not line or len(line.split()) > 12: return None
    if current_chapter_title is None: return None
    if is_likely_chapter_heading(line) or is_likely_metadata_or_footer(line): return None
    words = line.split()
    if 1 < len(words) < 12:
        is_title_case = line.istitle()
        cap_words = sum(1 for word in words if word[0].isupper())
        is_significantly_capitalized = cap_words / len(words) > 0.4
        has_no_end_punctuation = not line[-1] in ['.', '?', '!', ':', ',', ';']
        if (is_title_case or is_significantly_capitalized) and has_no_end_punctuation:
             if len(line) > 4:
                  return line.strip()
    return None


def is_likely_metadata_or_footer(line):
    """Basic heuristic to filter out metadata/footers/page numbers."""
    line = line.strip()
    if not line: return True
    cleaned_line = re.sub(r"^\W+|\W+$", "", line)
    # Now check if the cleaned line is *only* a digit - more robust for page numbers
    if cleaned_line.isdigit() and line == cleaned_line: # Check if the original was *just* the number
        return True
    if "www." in line or ".com" in line or "@" in line or "goodwordbooks" in line or "cpsglobal" in line: return True
    if re.match(r"^\s*Page\s+\d+\s*$", line, re.IGNORECASE): return True
    if "©" in line or "copyright" in line.lower() or "first published" in line.lower() or "isbn" in line.lower(): return True
    if "nizamuddin" in line.lower() or "new delhi" in line.lower() or "noida" in line.lower() or "bensalem" in line.lower(): return True # Specific addresses
    if "printed in" in line.lower(): return True
    if len(set(line.strip())) < 4 and len(line.strip()) > 4: return True # Decorative lines
    if line.endswith(cleaned_line) and cleaned_line.isdigit() and len(line) < 80 and len(line) > len(cleaned_line) + 2:
         if not re.search(r"[a-zA-Z]{4,}", line): return True # TOC Check
    # Removed the short uppercase line filter as it might catch headings
    return False

# --- Main Extraction Function (MODIFIED) ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    """
    Extracts text, cleans, splits sentences, tracks pages & detects headings,
    respecting page skips and offset.
    Returns a list of tuples: (text, page_num, chapter_title, subchapter_title)
    or None if an error occurs.
    """
    doc = None
    extracted_data = [] # Stores the tuples
    current_chapter_title_state = None # Tracks the active chapter

    try:
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")
        total_pages = len(doc)
        print(f"Total pages in PDF: {total_pages}") # Debug print

        for page_num_0based, page in enumerate(doc):

            # --- Page Skipping Logic ---
            if page_num_0based < start_skip:
                # print(f"Skipping page {page_num_0based+1} (start skip)") # Debug
                continue
            if page_num_0based >= total_pages - end_skip:
                # print(f"Skipping page {page_num_0based+1} (end skip)") # Debug
                break # Stop processing pages

            # --- Calculate Adjusted Page Number ---
            # This is the "real" page number according to the book's numbering
            adjusted_page_num = page_num_0based - start_skip + start_page_offset
            # print(f"Processing PDF page {page_num_0based+1} as book page {adjusted_page_num}") # Debug

            page_text = page.get_text("text", sort=True) # Enable sorting
            if not page_text: continue

            lines = page_text.split('\n')

            for line in lines:
                if is_likely_metadata_or_footer(line):
                    continue

                line_clean = line.strip()
                if not line_clean: continue

                chapter_heading = is_likely_chapter_heading(line_clean)
                subchapter_heading = None if chapter_heading else is_likely_subchapter_heading(line_clean, current_chapter_title_state)
                is_heading = chapter_heading or subchapter_heading

                if chapter_heading:
                    current_chapter_title_state = chapter_heading
                    extracted_data.append((chapter_heading, adjusted_page_num, chapter_heading, None))
                elif subchapter_heading:
                    extracted_data.append((subchapter_heading, adjusted_page_num, None, subchapter_heading))
                else:
                    try:
                        sentences_in_line = nltk.sent_tokenize(line_clean)
                        for sentence in sentences_in_line:
                            sentence_clean_again = sentence.strip()
                            if sentence_clean_again:
                                extracted_data.append((sentence_clean_again, adjusted_page_num, None, None))
                    except Exception as e:
                        print(f"Warning: NLTK error on page {adjusted_page_num}, line '{line_clean}': {e}")
                        if line_clean:
                            extracted_data.append((line_clean, adjusted_page_num, None, None))

        return extracted_data

    except Exception as e:
        print(f"ERROR in extract_sentences_with_structure: {e}")
        # Consider logging full traceback here
        return None
    finally:
        if doc: doc.close()
