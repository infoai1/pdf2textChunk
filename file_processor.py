# --- START OF FILE file_processor.py ---
import fitz  # PyMuPDF for PDF
import docx  # For DOCX
import re
import nltk
import io

# --- Metadata/Footer Check ---
def is_likely_metadata_or_footer(line):
    # (Keep as is - this function remains the same)
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
    # Added filter for very short uppercase lines (potential headers/footers missed)
    if len(line) < 15 and line.isupper() and not re.match(r"^\s*(CHAPTER|SECTION|PART)\s", line, re.IGNORECASE):
         return True
    return False


# --- Simplified Heading Checker ---
def check_heading_heuristics_simple(line_text, is_bold_hint, is_italic_hint, current_chapter_title):
    """
    Simplified heuristic focusing on Style, Title Case, and Length.
    Returns ('chapter', text), ('subchapter', text), or (None, None).
    """
    line_text = line_text.strip()
    words = line_text.split()
    num_words = len(words)

    if not line_text or num_words == 0: return None, None
    # Metadata check happens before calling this

    MAX_HEADING_WORDS = 9
    MIN_HEADING_WORDS = 1
    is_title_case = line_text.istitle()

    # Rule 1: Explicit Keywords
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", line_text, re.IGNORECASE) and num_words < 8:
        return 'chapter', line_text

    # Rule 2: Style + Title Case + Short = Likely Chapter
    if (is_bold_hint or is_italic_hint) and is_title_case and MIN_HEADING_WORDS <= num_words <= MAX_HEADING_WORDS:
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
             return 'chapter', line_text

    # Rule 3: Just Title Case + Short (Subchapter/Chapter Fallback)
    if is_title_case and MIN_HEADING_WORDS <= num_words <= MAX_HEADING_WORDS + 2:
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
             if current_chapter_title: return 'subchapter', line_text
             else: return 'chapter', line_text

    # Rule 4: Numbered lists
    if re.match(r"^\s*[IVXLCDM]+\.?\s+.{3,}", line_text) and num_words < 10: return 'chapter', line_text
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line_text) and num_words < 8: return 'chapter', line_text

    return None, None # Not detected


# --- Main Extraction Function (Handles PDF and DOCX) ---
def extract_sentences_with_structure(file_name, file_content, start_skip=0, end_skip=0, start_page_offset=1):
    """
    Extracts text from PDF or DOCX, cleans, splits sentences, tracks pages & detects headings.
    Returns a list of tuples: (text, page_num_marker, chapter_title, subchapter_title) or None.
    """
    extracted_data = []
    current_chapter_title_state = None
    page_counter = 0 # Generic counter for both formats

    file_extension = file_name.split('.')[-1].lower()
    print(f"Detected file type: {file_extension}")

    # --- PDF Processing ---
    if file_extension == 'pdf':
        doc = None
        try:
            doc = fitz.open(stream=file_content, filetype="pdf")
            total_pages = len(doc)
            print(f"Processing PDF with {total_pages} pages.")

            for page_num_0based, page in enumerate(doc):
                # Page Skipping
                if page_num_0based < start_skip: continue
                if page_num_0based >= total_pages - end_skip: break
                adjusted_page_num = page_num_0based - start_skip + start_page_offset
                page_marker = adjusted_page_num # Use adjusted page num for PDF

                try:
                    blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_PRESERVE_LIGATURES)["blocks"]
                    for b in blocks:
                        if b['type'] == 0: # Text block
                            for l in b["lines"]:
                                line_dict = l
                                line_text = "".join(s["text"] for s in l["spans"]).strip()
                                if not line_text or is_likely_metadata_or_footer(line_text): continue

                                # Get style hints
                                is_italic_hint = False; is_bold_hint = False
                                try:
                                    if l["spans"]:
                                        font_name = l["spans"][0].get('font', '').lower()
                                        flags = l["spans"][0].get('flags', 0)
                                        is_italic_hint = bool(flags & 1) or "italic" in font_name
                                        is_bold_hint = bool(flags & 4) or "bold" in font_name or "black" in font_name
                                except: pass

                                heading_type, heading_text = check_heading_heuristics_simple(
                                    line_text, is_bold_hint, is_italic_hint, current_chapter_title_state
                                )

                                is_heading = heading_type is not None

                                if heading_type == 'chapter':
                                    current_chapter_title_state = heading_text
                                    extracted_data.append((heading_text, page_marker, heading_text, None))
                                elif heading_type == 'subchapter':
                                    if current_chapter_title_state:
                                        extracted_data.append((heading_text, page_marker, None, heading_text))
                                    else: is_heading = False
                                else: is_heading = False

                                if not is_heading:
                                    try:
                                        sentences = nltk.sent_tokenize(line_text)
                                        for sentence in sentences:
                                            sc = sentence.strip();
                                            if sc: extracted_data.append((sc, page_marker, None, None))
                                    except Exception as e: print(f"Warn: NLTK err PDF Pg {page_marker}: {e}"); extracted_data.append((line_text, page_marker, None, None))

                except Exception as e_page:
                    print(f"Error processing PDF page {adjusted_page_num}: {e_page}")
                    continue # Skip to next page
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

                # Approximate style hints
                is_bold_hint = any(run.bold for run in para.runs if run.text.strip())
                is_italic_hint = any(run.italic for run in para.runs if run.text.strip())

                heading_type, heading_text = check_heading_heuristics_simple(
                    line_text, is_bold_hint, is_italic_hint, current_chapter_title_state
                )

                is_heading = heading_type is not None

                if heading_type == 'chapter':
                    current_chapter_title_state = heading_text
                    extracted_data.append((heading_text, page_marker, heading_text, None))
                elif heading_type == 'subchapter':
                     if current_chapter_title_state:
                         extracted_data.append((heading_text, page_marker, None, heading_text))
                     else: is_heading = False
                else: is_heading = False

                if not is_heading:
                    try:
                        sentences = nltk.sent_tokenize(line_text)
                        for sentence in sentences:
                            sc = sentence.strip()
                            if sc: extracted_data.append((sc, page_marker, None, None))
                    except Exception as e: print(f"Warn: NLTK err DOCX Para {page_marker}: {e}"); extracted_data.append((line_text, page_marker, None, None))

        except Exception as e_main:
            print(f"Main DOCX Extraction Error: {e_main}"); return None

    else:
        print(f"Error: Unsupported file type: .{file_extension}")
        # Use st.error in the main app instead
        # st.error(f"Unsupported file type: .{file_extension}. Please upload PDF or DOCX.")
        return None

    print(f"Extraction complete. Found {len(extracted_data)} items.")
    return extracted_data

# --- END OF FILE file_processor.py ---
