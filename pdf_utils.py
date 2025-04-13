import fitz  # PyMuPDF
import re
import nltk
import streamlit as st # Keep for st.info/success/error during download only

# --- NLTK Download Logic (Keep as is from previous version) ---
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

# --- Heuristics for Structure Detection (REVISED & NEEDS TUNING) ---
def is_likely_chapter_heading(line):
    """Guess if a line is a chapter heading. Returns the heading text or None."""
    line = line.strip()
    if not line or len(line.split()) > 10: return None # Skip empty or long lines

    # Strong indicators first
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+[:\.\s]*", line, re.IGNORECASE): return line.strip()
    if re.match(r"^\s*[IVXLCDM]+\.\s+.{3,}", line): return line.strip() # Roman numeral followed by text
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line) and len(line.split()) < 8: return line.strip() # Numbered heading

    # Weaker indicators (Tune based on your specific book style)
    # Assume chapter titles might be Title Case OR All Caps, and relatively short
    words = line.split()
    if 1 < len(words) < 8:
        is_title_case = line.istitle()
        is_all_caps = line.isupper() and len(line) > 3 # Avoid short acronyms
        has_no_end_punctuation = not line[-1] in ['.', '?', '!', ':', ',', ';']

        if (is_title_case or is_all_caps) and has_no_end_punctuation:
             # Add extra check: Does it NOT look like a normal sentence fragment?
             # e.g., avoid lines starting with lowercase unless they are very short like "of"
             if not (line[0].islower() and len(words)>1):
                  return line.strip()
    return None

def is_likely_subchapter_heading(line, current_chapter_title):
    """Guess if a line is a subchapter heading."""
    line = line.strip()
    if not line or len(line.split()) > 12: return None # Empty or too long
    if current_chapter_title is None: return None # Cannot have subchapter without chapter context
    if is_likely_chapter_heading(line) or is_likely_metadata_or_footer(line): return None

    # Look for Title Case, maybe slightly longer than chapter, no end punctuation
    words = line.split()
    if 1 < len(words) < 12:
        is_title_case = line.istitle()
        # Check for significant capitalization (more than just first word)
        cap_words = sum(1 for word in words if word[0].isupper())
        is_significantly_capitalized = cap_words / len(words) > 0.4

        has_no_end_punctuation = not line[-1] in ['.', '?', '!', ':', ',', ';']

        if (is_title_case or is_significantly_capitalized) and has_no_end_punctuation:
             # Avoid single-word uppercase lines unless very specific
             if len(line) > 4: # Min length for a potential subheading
                  return line.strip()
    return None


def is_likely_metadata_or_footer(line):
    """More aggressive heuristic to filter out metadata/footers/page numbers."""
    line = line.strip()
    if not line: return True

    # Page numbers (allow optional surrounding non-alphanumeric chars)
    cleaned_line = re.sub(r"^\W+|\W+$", "", line) # Remove leading/trailing non-word chars
    if cleaned_line.isdigit() and len(cleaned_line) < 4: return True # Allow up to 3 digits for page nums

    # Common contact/publishing info
    if "www." in line or ".com" in line or "@" in line or "goodwordbooks" in line or "cpsglobal" in line: return True
    if "nizamuddin" in line.lower() or "new delhi" in line.lower() or "noida" in line.lower() or "bensalem" in line.lower(): return True # Specific addresses
    if "printed in" in line.lower(): return True
    if re.match(r"^\s*Page\s+\d+\s*$", line, re.IGNORECASE): return True
    if "©" in line or "copyright" in line.lower() or "first published" in line.lower() or "isbn" in line.lower(): return True
    if "international" in line.lower() and len(line.split()) < 5: return True # Short lines with this might be publisher parts
    if line.lower() == "goodword" or line.lower() == "cps international": return True

    # Simple TOC checks (often Name ........ PageNum)
    if re.search(r'\.{5,}\s*\d+$', line): return True # Multiple dots followed by number

    # Very short lines consisting of only uppercase/symbols/numbers (likely headers/footers)
    if len(line) < 20 and re.match(r"^[\sA-Z\d\W]+$", line) and not re.search(r'[a-z]', line):
         # Check if it's not a likely ALL CAPS chapter heading detected above
         if not is_likely_chapter_heading(line):
              return True

    return False


# --- Main Extraction Function (Minor Change for Clarity) ---
def extract_sentences_with_structure(uploaded_file_content):
    """
    Extracts text, cleans, splits sentences, tracks pages & detects headings.
    Returns a list of tuples: (text, page_num, chapter_title, subchapter_title)
    where chapter/subchapter title is only present on the line it's detected.
    """
    doc = None
    extracted_data = [] # Stores the tuples
    current_chapter_title_state = None # Tracks the active chapter

    try:
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")

        for page_num_0based, page in enumerate(doc):
            page_num = page_num_0based + 1
            page_text = page.get_text("text", sort=True) # Enable sorting for better line ordering
            if not page_text: continue

            lines = page_text.split('\n')

            for line in lines:
                # First, check if it's metadata/footer
                if is_likely_metadata_or_footer(line):
                    continue # Skip entirely

                line_clean = line.strip()
                if not line_clean: continue

                # Now, check for headings
                chapter_heading = is_likely_chapter_heading(line_clean)
                subchapter_heading = None
                is_heading = False

                if chapter_heading:
                    current_chapter_title_state = chapter_heading # Update chapter state
                    extracted_data.append((chapter_heading, page_num, chapter_heading, None))
                    is_heading = True
                else:
                    # Only check for subchapter if we are inside a chapter
                    subchapter_heading = is_likely_subchapter_heading(line_clean, current_chapter_title_state)
                    if subchapter_heading:
                        extracted_data.append((subchapter_heading, page_num, None, subchapter_heading))
                        is_heading = True

                # If it wasn't a heading, process as regular text
                if not is_heading:
                    try:
                        sentences_in_line = nltk.sent_tokenize(line_clean)
                        for sentence in sentences_in_line:
                            sentence_clean_again = sentence.strip()
                            if sentence_clean_again:
                                # Regular sentence tuple has None for headings
                                extracted_data.append((sentence_clean_again, page_num, None, None))
                    except Exception as e:
                        print(f"Warning: NLTK error on page {page_num}, line '{line_clean}': {e}")
                        if line_clean: # Append raw line as fallback
                            extracted_data.append((line_clean, page_num, None, None))

        return extracted_data

    except Exception as e:
        print(f"ERROR in extract_sentences_with_structure: {e}")
        # Consider logging the full traceback here
        return None
    finally:
        if doc: doc.close()
