# --- START OF FILE file_processor.py ---
import fitz
import re
import nltk
import io
import streamlit as st # Only for potential NLTK errors

# --- NLTK Download Logic ---
# (Keep as is - can be in utils.py or here if only used here)
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
        st.error(f"NLTK Find Error ({resource_name}): {e_find}")
        return False
    return True


# --- Metadata/Footer Check ---
def is_likely_metadata_or_footer(line):
    # (Keep as is from previous version)
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
    # Filter short uppercase lines unless clearly a heading keyword
    if len(line) < 15 and line.isupper() and not re.match(r"^\s*(CHAPTER|SECTION|PART)\s", line, re.IGNORECASE):
        # Check word count - allow short acronyms maybe?
        if len(line.split()) > 1 and not line.istitle() : # If multiple words and not title case, likely header/footer
            return True
    return False


# --- HEADING CHECKER BASED ON USER CRITERIA ---
def check_heading_user_defined(
    line_dict,              # Dictionary for PDF line (contains bbox, spans)
    line_text,              # Plain text of the line/paragraph
    page_width,             # Width of the PDF page (for centering)
    is_single_line_block,   # Is this line alone in its block (PDF)?
    is_bold_hint,           # Is the DOCX paragraph bold?
    is_italic_hint,         # Is the DOCX paragraph italic?
    heading_criteria        # Dictionary of user selections from UI
    ):
    """
    Checks if a line matches user-defined heading criteria.
    Returns detected chapter title text or None. (No subchapter differentiation).
    """
    words = line_text.split()
    num_words = len(words)

    # Basic cleanup / metadata check
    if not line_text or num_words == 0: return None
    if is_likely_metadata_or_footer(line_text): return None

    # --- Apply User Selected Criteria ---

    # Length Check
    if heading_criteria['use_length']:
        if not (heading_criteria['min_words'] <= num_words <= heading_criteria['max_words']):
            return None # Fails length constraint

    # Keyword Check
    if heading_criteria['keyword_pattern']:
        try:
            if not re.search(heading_criteria['keyword_pattern'], line_text, re.IGNORECASE):
                return None # Fails keyword constraint
        except re.error: # Handle invalid regex from user - treat as no match
            return None

    # Isolation Check (Only reliable for PDF via is_single_line_block)
    if heading_criteria['require_isolated'] and not is_single_line_block:
        # For DOCX, this check is effectively ignored as is_single_line_block will be False
        if line_dict is not None: # Check if we have PDF line dict info
             return None # Fails isolation constraint for PDF

    # Centering Check (Approximate - Primarily for PDF)
    if heading_criteria['require_centered']:
        is_centered_hint = False
        if line_dict and 'bbox' in line_dict and page_width > 0:
            bbox = line_dict['bbox']
            left = bbox[0]; right = bbox[2]
            # Use generous centering tolerance from previous attempts
            if abs(left - (page_width - right)) < (page_width * 0.20) and left > (page_width * 0.15):
                is_centered_hint = True
        # For DOCX, this check cannot be reliably performed here, so we might pass?
        # Or fail if centering is required? Let's fail for now if required.
        elif line_dict is None: # We are likely processing DOCX
             pass # Cannot verify centering for DOCX here easily
        if line_dict and not is_centered_hint: # If PDF and not centered
             return None # Fails centering constraint


    # --- Style & Case Checks ---
    # Get style info (might be hints for DOCX)
    line_is_italic = is_italic_hint
    line_is_bold = is_bold_hint
    if line_dict: # If PDF, extract from spans
        try:
            valid_spans = [s for s in line_dict["spans"] if s['text'].strip()]
            if valid_spans:
                total_chars = sum(len(s['text'].strip()) for s in valid_spans)
                italic_chars = 0; bold_chars = 0
                for s in valid_spans:
                    flags = s.get('flags', 0)
                    font_name = s.get('font','').lower()
                    span_len = len(s['text'].strip())
                    if flags & 1 or "italic" in font_name: italic_chars += span_len
                    if flags & 4 or "bold" in font_name or "black" in font_name: bold_chars += span_len
                if total_chars > 0:
                    line_is_italic = (italic_chars / total_chars) > 0.6
                    line_is_bold = (bold_chars / total_chars) > 0.6
        except Exception: pass # Ignore errors getting detailed flags

    # Apply required style checks
    if heading_criteria['require_italic'] and not line_is_italic: return None
    if heading_criteria['require_bold'] and not line_is_bold: return None

    # Apply required case checks
    is_line_title_case = line_text.istitle()
    is_line_all_caps = line_text.isupper() and re.search("[A-Z]", line_text) # Check it has letters

    if heading_criteria['require_title_case'] and not is_line_title_case: return None
    if heading_criteria['require_all_caps'] and not is_line_all_caps: return None
    # Handle conflict if both are required (unlikely UI state but good practice)
    if heading_criteria['require_title_case'] and heading_criteria['require_all_caps']:
        if not (is_line_title_case and is_line_all_caps): # Mostly relevant for single-word titles
             if num_words > 1: return None # Cannot be both if multiple words

    # If all required checks passed, it's a heading!
    # print(f"✅ Matched Heading: {line_text}") # Debug
    return line_text # Return the heading text

# --- Main Extraction Function ---
def extract_sentences_with_structure(
    file_name, file_content,
    heading_criteria, # Pass the dictionary of user choices
    start_skip=0, end_skip=0, start_page_offset=1
    ):
    """
    Extracts text, cleans, splits sentences, tracks pages & detects headings
    based on user-provided criteria.
    Returns list of tuples: (text, page_marker, detected_chapter_title)
    """
    doc = None
    extracted_data = []
    current_chapter_title_state = None

    file_extension = file_name.split('.')[-1].lower()

    # --- PDF Processing ---
    if file_extension == 'pdf':
        try:
            doc = fitz.open(stream=file_content, filetype="pdf")
            total_pages = len(doc)

            for page_num_0based, page in enumerate(doc):
                if page_num_0based < start_skip: continue
                if page_num_0based >= total_pages - end_skip: break
                adjusted_page_num = page_num_0based - start_skip + start_page_offset
                page_marker = adjusted_page_num
                page_width = page.rect.width

                try:
                    blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_PRESERVE_LIGATURES)["blocks"]
                    for b in blocks:
                        if b['type'] == 0:
                            is_single_line_block = len(b['lines']) == 1
                            for l in b["lines"]:
                                line_dict = l
                                line_text = "".join(s["text"] for s in l["spans"]).strip()
                                if not line_text or is_likely_metadata_or_footer(line_text): continue

                                # Check heading using user criteria
                                heading_text = check_heading_user_defined(
                                    line_dict, line_text, page_width, is_single_line_block,
                                    False, False, # Style hints not needed directly here
                                    heading_criteria
                                )

                                if heading_text is not None:
                                    current_chapter_title_state = heading_text
                                    extracted_data.append((heading_text, page_marker, heading_text))
                                else: # Regular text
                                    try:
                                        sentences = nltk.sent_tokenize(line_text)
                                        for sentence in sentences:
                                            sc = sentence.strip()
                                            if sc: extracted_data.append((sc, page_marker, None))
                                    except Exception as e: print(f"Warn: NLTK err PDF Pg {page_marker}: {e}"); extracted_data.append((line_text, page_marker, None))
                except Exception as e_page: print(f"Error processing PDF page {adjusted_page_num}: {e_page}")
        except Exception as e_main: print(f"Main PDF Extraction Error: {e_main}"); return None
        finally:
            if doc: doc.close()

    # --- DOCX Processing ---
    elif file_extension == 'docx':
        try:
            document = docx.Document(io.BytesIO(file_content))
            paragraph_index = 0
            for para in document.paragraphs:
                paragraph_index += 1
                page_marker = f"Para_{paragraph_index}"
                line_text = para.text.strip()
                if not line_text or is_likely_metadata_or_footer(line_text): continue

                is_bold_hint = any(run.bold for run in para.runs if run.text.strip())
                is_italic_hint = any(run.italic for run in para.runs if run.text.strip())

                heading_text = check_heading_user_defined(
                    None, line_text, 0, # No line_dict, page_width for DOCX
                    False, # Assume not single line block
                    is_bold_hint, is_italic_hint, # Pass style hints
                    heading_criteria
                )

                if heading_text is not None:
                    current_chapter_title_state = heading_text
                    extracted_data.append((heading_text, page_marker, heading_text))
                else: # Regular text
                    try:
                        sentences = nltk.sent_tokenize(line_text)
                        for sentence in sentences:
                            sc = sentence.strip()
                            if sc: extracted_data.append((sc, page_marker, None))
                    except Exception as e: print(f"Warn: NLTK err DOCX Para {page_marker}: {e}"); extracted_data.append((line_text, page_marker, None))
        except Exception as e_main: print(f"Main DOCX Extraction Error: {e_main}"); return None

    else: print(f"Error: Unsupported file type: .{file_extension}"); return None

    print(f"Extraction complete. Found {len(extracted_data)} items.")
    return extracted_data

# --- END OF FILE file_processor.py ---
