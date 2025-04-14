# --- START OF FILE file_processor.py ---
import fitz  # PyMuPDF for PDF
import docx  # For DOCX
import re
import nltk
import io
import streamlit as st # Use for error reporting

# --- NLTK Download Logic ---
# (Keep as is)
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
            st.error(f"Download Error: Failed for NLTK '{resource_name}'. Error: {e}")
            return False
    except Exception as e_find:
        st.error(f"NLTK Find Error ({name}): {e_find}")
        return False
    return True


# --- Metadata/Footer Check ---
# (Keep as is)
def is_likely_metadata_or_footer(line):
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
         # Check if it doesn't look like a likely heading based on case/style
         if not line.istitle(): # If it's all caps and short, likely footer/header unless explicitly Chapter etc.
              return True
    return False


# --- Simplified Heading Checker ---
# (Keep check_heading_heuristics_simple as is from v13)
def check_heading_heuristics_simple(line_text, is_bold_hint, is_italic_hint, current_chapter_title):
    line_text = line_text.strip()
    words = line_text.split()
    num_words = len(words)
    if not line_text or num_words == 0: return None, None
    # Metadata check happens before calling this now
    MAX_HEADING_WORDS = 9; MIN_HEADING_WORDS = 1; is_title_case = line_text.istitle()
    # Rule 1: Explicit Keywords
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", line_text, re.IGNORECASE) and num_words < 8: return 'chapter', line_text
    # Rule 2: Style + Title Case + Short
    if (is_bold_hint or is_italic_hint) and is_title_case and MIN_HEADING_WORDS <= num_words <= MAX_HEADING_WORDS:
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']: return 'chapter', line_text
    # Rule 3: Just Title Case + Short
    if is_title_case and MIN_HEADING_WORDS <= num_words <= MAX_HEADING_WORDS + 2:
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']:
             if current_chapter_title: return 'subchapter', line_text
             else: return 'chapter', line_text
    # Rule 4: Numbered lists
    if re.match(r"^\s*[IVXLCDM]+\.?\s+.{3,}", line_text) and num_words < 10: return 'chapter', line_text
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line_text) and num_words < 8: return 'chapter', line_text
    return None, None


# --- Main Extraction Function (Handles PDF and DOCX) ---
def extract_sentences_with_structure(file_name, file_content, start_skip=0, end_skip=0, start_page_offset=1):
    extracted_data = []
    current_chapter_title_state = None
    page_counter = 0

    file_extension = file_name.split('.')[-1].lower()
    print(f"Detected file type: {file_extension}")

    # --- PDF Processing ---
    if file_extension == 'pdf':
        doc = None
        try:
            # ... (Keep PDF processing block exactly as in v13) ...
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
                                    if current_chapter_title_state: extracted_data.append((heading_text, page_marker, None, heading_text))
                                    else: is_heading = False
                                else: is_heading = False

                                if not is_heading:
                                    try:
                                        sentences = nltk.sent_tokenize(line_text)
                                        for sentence in sentences:
                                            sc = sentence.strip();
                                            if sc: extracted_data.append((sc, page_marker, None, None))
                                    except Exception as e_nltk: print(f"Warn: NLTK err PDF Pg {page_marker}: {e_nltk}"); extracted_data.append((line_text, page_marker, None, None))
                except Exception as e_page:
                    st.error(f"Error processing PDF page {adjusted_page_num}: {e_page}") # Use st.error
                    continue
        except Exception as e_main:
            st.error(f"Main PDF Extraction Error: {e_main}"); st.exception(e_main); return None # Use st.error
        finally:
            if doc: doc.close()

    # --- DOCX Processing ---
    elif file_extension == 'docx':
        try:
            # --- ADD TRY-EXCEPT AROUND OPENING THE DOCX ---
            try:
                file_stream = io.BytesIO(file_content)
                document = docx.Document(file_stream)
                print(f"Processing DOCX file...")
            except Exception as e_open_docx:
                st.error(f"Error opening DOCX file: {e_open_docx}. Is it a valid .docx file?")
                return None # Stop if opening fails
            # --- END DOCX OPENING TRY-EXCEPT ---

            paragraph_index = 0
            for para in document.paragraphs:
                paragraph_index += 1
                page_marker = f"Para_{paragraph_index}"
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
                    except Exception as e_nltk: print(f"Warn: NLTK err DOCX Para {page_marker}: {e_nltk}"); extracted_data.append((line_text, page_marker, None, None))

        except Exception as e_main:
            st.error(f"Main DOCX Extraction Error: {e_main}"); st.exception(e_main); return None

    else:
        st.error(f"Unsupported file type: .{file_extension}. Please upload PDF or DOCX.")
        return None

    print(f"Extraction complete. Found {len(extracted_data)} items.")
    return extracted_data

# --- END OF FILE file_processor.py ---
