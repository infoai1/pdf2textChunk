import fitz  # PyMuPDF
import re
import nltk
import streamlit as st # Keep for st.info/success/error during download only

# --- NLTK Download Logic ---
def download_nltk_data(resource_name, resource_path):
    """Helper to download NLTK data if needed. Called from app.py."""
    try:
        nltk.data.find(resource_path)
    except LookupError:
        # Use Streamlit only for user feedback during setup
        st.info(f"Downloading NLTK data package: '{resource_name}'...")
        try:
            nltk.download(resource_name, quiet=True)
            st.success(f"NLTK data '{resource_name}' downloaded.")
            return True # Indicate success
        except Exception as e:
            st.error(f"Failed to download NLTK '{resource_name}' data: {e}")
            return False # Indicate failure
    except Exception as e_find:
        st.error(f"An error occurred checking for NLTK data '{resource_name}': {e_find}")
        return False # Indicate failure
    return True # Indicate resource already exists

# --- Heuristics (Keep these together with the extraction logic) ---
def is_likely_chapter_heading(line):
    """Guess if a line is a chapter heading. Returns the heading text or None."""
    line = line.strip()
    if not line or len(line) > 100: return None
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", line, re.IGNORECASE): return line
    if re.match(r"^\s*[IVXLCDM]+\.?\s+", line) and len(line.split()) < 10 : return line # Roman numerals check
    if re.match(r"^\s*\d+\.?\s+[A-Z]", line) and len(line.split()) < 10:
         words = line.split()
         # Check if it looks like a title and has few words
         if len(words) > 1 and sum(1 for word in words[1:] if word.istitle() or word.isupper()) >= len(words[1:]) * 0.5:
              return line
    if 1 < len(line.split()) < 7 and line.isupper() and len(line) > 3: return line
    # Check for short Title Case lines without ending punctuation
    if line.istitle() and 1 < len(line.split()) < 10 and not line[-1] in ['.', '?', '!', ':', ',']:
        return line
    return None

def is_likely_subchapter_heading(line, current_chapter_title):
    """Guess if a line is a subchapter heading."""
    line = line.strip()
    if not line or len(line) > 120: return None
    # Basic checks: not a chapter, not metadata, within a chapter context
    if is_likely_chapter_heading(line) or is_likely_metadata_or_footer(line) or current_chapter_title is None:
        return None
    # Title case, relatively short, no sentence-ending punctuation
    line_words = line.split()
    if 1 < len(line_words) < 12 and not line[-1] in ['.', '?', '!', ':', ',']:
        # Check if looks like Title Case or has significant capitalization
        if line.istitle() or (sum(1 for word in line_words if word.istitle() or word.isupper()) >= len(line_words) * 0.4):
            if len(line) > 4: # Avoid very short potential false positives
                 return line
    return None

def is_likely_metadata_or_footer(line):
    """Basic heuristic to filter out metadata/footers/page numbers."""
    line = line.strip()
    if not line: return True
    cleaned_line = re.sub(r"^[\s\-—_]+|[\s\-—_]+$", "", line)
    if cleaned_line.isdigit(): return True
    if "www." in line or ".com" in line or "@" in line or "goodwordbooks" in line or "cpsglobal" in line: return True
    if re.match(r"^\s*Page\s+\d+\s*$", line, re.IGNORECASE): return True
    if "©" in line or "Copyright" in line or re.match(r"^\s*First Published", line) or "ISBN" in line: return True
    if len(set(line.strip())) < 4 and len(line.strip()) > 4: return True # Decorative lines
    # Basic TOC check
    if line.endswith(cleaned_line) and cleaned_line.isdigit() and len(line) < 80 and len(line) > len(cleaned_line) + 2:
         if not re.search(r"[a-zA-Z]{4,}", line): return True # Likely TOC if no long words
    # Filter lines that are mostly uppercase and very short (like headers maybe)
    if len(line) < 15 and line.isupper(): return True
    return False

# --- Main Extraction Function ---
def extract_sentences_with_structure(uploaded_file_content):
    """
    Extracts text, cleans, splits sentences, tracks pages & detects headings.
    Returns a list of tuples: (text, page_num, chapter_title, subchapter_title)
    or None if an error occurs. Chapter/Subchapter titles are only filled on the
    line they are detected.
    """
    doc = None
    sentences_structure = []
    current_chapter_title_state = None

    try:
        # Open PDF from bytes content
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")

        for page_num_0based, page in enumerate(doc):
            page_num = page_num_0based + 1
            page_text = page.get_text("text")
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
                    # Append the heading itself with its structural info
                    sentences_structure.append((chapter_heading, page_num, chapter_heading, None))
                elif subchapter_heading:
                     # Append the heading itself with its structural info
                    sentences_structure.append((subchapter_heading, page_num, None, subchapter_heading))
                else:
                    # Process as regular text / sentences
                    try:
                        sentences_in_line = nltk.sent_tokenize(line_clean)
                        for sentence in sentences_in_line:
                            sentence_clean_again = sentence.strip()
                            if sentence_clean_again:
                                sentences_structure.append((sentence_clean_again, page_num, None, None))
                    except Exception as e:
                        # Log or handle sentence tokenization error - maybe append raw line?
                        print(f"Warning: NLTK failed on line: '{line_clean}' on page {page_num}. Error: {e}")
                        if line_clean:
                            sentences_structure.append((line_clean, page_num, None, None))

        return sentences_structure

    except Exception as e:
        # Log the error properly instead of using st.error directly
        print(f"ERROR in extract_sentences_with_structure: {e}")
        # Optionally raise a custom exception
        return None
    finally:
        if doc: doc.close()
