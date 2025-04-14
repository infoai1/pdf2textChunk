# --- START OF FILE file_processor.py ---
import fitz
import re
import nltk
import io
# Removed statistics import, simplified font usage
import streamlit as st # Keep for error reporting if needed directly

# --- Metadata/Footer Check ---
def is_likely_metadata_or_footer(line):
    # (Keep as is)
    line = line.strip()
    if not line: return True
    cleaned_line = re.sub(r"^\W+|\W+$", "", line)
    if cleaned_line.isdigit() and line == cleaned_line and len(cleaned_line) < 4 : return True
    if "www." in line or ".com" in line or "@" in line or "books" in line.lower() or "global" in line.lower() or ("center" in line.lower() and "peace" in line.lower()):
         if len(line.split()) < 12: return True
    if re.match(r"^\s*Page\s+\d+\s*$", line, re.IGNORECASE): return True
    if "©" in line or "copyright" in line.lower() or "first published" in line.lower() or "isbn" in line.lower(): return True
    if "printed in" in line.lower(): return True
    if any(loc in line.lower() for loc in ["nizamuddin", "new delhi", "noida", "bensalem", "byberry road"]): return True
    if len(set(line.strip())) < 4 and len(line.strip()) > 4: return True
    if line.endswith(cleaned_line) and cleaned_line.isdigit() and len(line) < 80 and len(line) > len(cleaned_line) + 2:
         if not re.search(r"[a-zA-Z]{4,}", line): return True
    return False

# --- Simplified Chapter Heading Checker ---
def check_if_chapter_heading(line_dict):
    """
    Simplified heuristic focusing on Style (italic/bold font name), Title Case, and Length.
    Returns detected chapter title text or None.
    """
    line_text = "".join(s["text"] for s in line_dict["spans"]).strip()
    words = line_text.split()
    num_words = len(words)

    if not line_text or num_words == 0: return None
    if is_likely_metadata_or_footer(line_text): return None # Check metadata first

    # --- Extract Style/Case ---
    is_italic_hint = False
    is_bold_hint = False
    is_title_case = line_text.istitle()

    try: # Check first span font name for style hints
        if line_dict["spans"]:
            font_name = line_dict["spans"][0].get('font', '').lower()
            is_italic_hint = "italic" in font_name
            is_bold_hint = "bold" in font_name or "black" in font_name
    except Exception: pass

    # --- Rule Prioritization ---
    MAX_HEADING_WORDS = 9 # Adjusted slightly
    MIN_HEADING_WORDS = 1 # Allow single words

    # Rule 1: Explicit Keywords
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", line_text, re.IGNORECASE) and num_words < 8:
        return line_text

    # Rule 2: Style (Italic/Bold Hint) + Title Case + Short
    if (is_italic_hint or is_bold_hint) and is_title_case and MIN_HEADING_WORDS <= num_words <= MAX_HEADING_WORDS:
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
             return line_text

    # Rule 3: Just Title Case + Short
    if is_title_case and MIN_HEADING_WORDS <= num_words <= MAX_HEADING_WORDS:
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
             return line_text

    # Rule 4: Numbered lists
    if re.match(r"^\s*[IVXLCDM]+\.?\s+.{3,}", line_text) and num_words < 10: return line_text
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line_text) and num_words < 8: return line_text

    return None # Not detected as heading

# --- Main Extraction Function ---
def extract_sentences_with_structure(file_name, file_content, start_skip=0, end_skip=0, start_page_offset=1):
    """
    Extracts text from PDF or DOCX, cleans, splits sentences, tracks pages & detects headings.
    Returns a list of tuples: (text, page_num_marker, detected_chapter_title) or None.
    """
    extracted_data = []
    current_chapter_title_state = None # Track last detected chapter title
    doc = None # Initialize doc

    file_extension = file_name.split('.')[-1].lower()
    print(f"Detected file type: {file_extension}")

    # --- PDF Processing ---
    if file_extension == 'pdf':
        try:
            doc = fitz.open(stream=file_content, filetype="pdf")
            total_pages = len(doc)
            print(f"Processing PDF with {total_pages} pages.")

            for page_num_0based, page in enumerate(doc):
                if page_num_0based < start_skip: continue
                if page_num_0based >= total_pages - end_skip: break
                adjusted_page_num = page_num_0based - start_skip + start_page_offset
                page_marker = adjusted_page_num

                try:
                    blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_PRESERVE_LIGATURES)["blocks"]
                    for b in blocks:
                        if b['type'] == 0:
                            for l in b["lines"]:
                                line_dict = l
                                line_text = "".join(s["text"] for s in l["spans"]).strip()
                                if not line_text or is_likely_metadata_or_footer(line_text): continue

                                heading_text = check_if_chapter_heading(line_dict) # Use simplified checker

                                if heading_text is not None:
                                    current_chapter_title_state = heading_text
                                    extracted_data.append((heading_text, page_marker, heading_text))
                                else: # Regular text
                                    try:
                                        sentences = nltk.sent_tokenize(line_text)
                                        for sentence in sentences:
                                            sc = sentence.strip()
                                            if sc: extracted_data.append((sc, page_marker, None))
                                    except Exception as e_nltk:
                                        print(f"Warn: NLTK err PDF Pg {page_marker}: {e_nltk}")
                                        if line_text: extracted_data.append((line_text, page_marker, None))
                except Exception as e_page:
                    print(f"Error processing PDF page {adjusted_page_num}: {e_page}")
                    continue
        except Exception as e_main:
            print(f"Main PDF Extraction Error: {e_main}"); return None
        finally:
            if doc: doc.close()

    # --- DOCX Processing ---
    elif file_extension == 'docx':
        try:
            document = docx.Document(io.BytesIO(file_content))
            print(f"Processing DOCX file.")
            paragraph_index = 0

            for para in document.paragraphs:
                paragraph_index += 1
                page_marker = f"Para_{paragraph_index}" # Use paragraph index as marker
                line_text = para.text.strip()
                if not line_text or is_likely_metadata_or_footer(line_text): continue

                # Approximate style hints from runs
                is_bold_hint = any(run.bold for run in para.runs if run.text.strip())
                is_italic_hint = any(run.italic for run in para.runs if run.text.strip())

                # Create a pseudo line_dict for the heuristic function
                # NOTE: Font name/size info isn't directly comparable to PDF here
                pseudo_line_dict = {'spans': [{'text': line_text, 'font': ('italic' if is_italic_hint else '') + ('bold' if is_bold_hint else '')}]}

                heading_text = check_if_chapter_heading(pseudo_line_dict) # Use simplified checker

                if heading_text is not None:
                    current_chapter_title_state = heading_text
                    extracted_data.append((heading_text, page_marker, heading_text))
                else: # Regular text
                    try:
                        sentences = nltk.sent_tokenize(line_text)
                        for sentence in sentences:
                            sc = sentence.strip()
                            if sc: extracted_data.append((sc, page_marker, None))
                    except Exception as e_nltk: print(f"Warn: NLTK err DOCX Para {page_marker}: {e_nltk}"); extracted_data.append((line_text, page_marker, None))

        except Exception as e_main:
            print(f"Main DOCX Extraction Error: {e_main}"); return None

    else:
        print(f"Error: Unsupported file type: .{file_extension}")
        return None

    print(f"Extraction complete. Found {len(extracted_data)} items.")
    return extracted_data

# --- END OF FILE file_processor.py ---
