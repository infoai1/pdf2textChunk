# --- START

            for page_num_0based, page in enumerate(doc):
                if page_num_0based < start_skip: continue
                if page_num_0based >= total_pages - end_skip OF FILE file_processor.py ---
import fitz
import re
import nltk
import io
import streamlit as st # Only for potential NLTK errors: break
                adjusted_page_num = page_num_0based - start_skip + start_page_offset
                page_marker =

# --- Metadata/Footer Check ---
# (Keep as is)
def is_likely_metadata_or_footer(line):
    line adjusted_page_num
                page_width = page.rect.width

                try:
                    blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_PRE = line.strip()
    if not line: return True
    cleaned_line = re.sub(r"^\W+|\W+$", "",SERVE_LIGATURES)["blocks"]
                    for b_idx, b in enumerate(blocks):
                        if b['type'] == 0: # Text block
                            is_single_line_block = len(b[' line)
    if cleaned_line.isdigit() and line == cleaned_line and len(cleaned_line) < 4 : return True
    if "www." in line or ".com" in line or "@" in line or "books" in line.lower() or "global" in linelines']) == 1
                            for l_idx, l in enumerate(b["lines"]):
                                line_dict = l
                                line_text_raw = "".join.lower() or ("center" in line.lower() and "peace" in line.lower()):
         if len(line.split()) < 12: return True
    if re.match(r"^\s(s["text"] for s in l["spans"]).strip() # Get raw first

                                if not line_text_raw or is_likely_metadata_*Page\s+\d+\s*$", line, re.IGNORECASE): return True
    if "©" in line or "copyright" inor_footer(line_text_raw): continue

                                # Check heading using user criteria line.lower() or "first published" in line.lower() or "isbn" in line.lower(): return True
    if "printed in"
                                heading_type, heading_text = check_heading_user_defined(
                                    line_dict, page_width, is_single_line in line.lower(): return True
    if any(loc in line.lower() for loc in ["nizamuddin", "new delhi", "n_block, **heading_criteria
                                )

                                if heading_type ==oida", "bensalem", "byberry road"]): return True
    if len(set(line.strip())) < 4 and len(line 'chapter':
                                    current_chapter_title_state = heading_.strip()) > 4: return True
    if line.endswith(cleaned_line) and cleaned_line.isdigit() and len(line)text
                                    extracted_data.append((heading_text, page_marker, heading < 80 and len(line) > len(cleaned_line)_text)) # (text, marker, chapter_title)
                                else + 2:
         if not re.search(r"[a-zA-Z]{4,}", line): return True
    return False

# --- Heading Checker Based on User Hint ---
def check_heading_user: # Regular text
                                    try:
                                        sentences = nltk.sent_tokenize(line_text_raw) # Tokenize raw text
                                        for sentence in sentences:
                                            sc = sentence.strip();
                                            if sc: extracted_data.append((sc, page_marker, None))_guided(
    line_dict,       # Dictionary for PDF line (contains bbox, spans)
    line_text,       # Plain text of # No chapter title for sentences
                                    except Exception as e_nltk:
                                        print(f"Warn: NLTK err PDF Pg {page the line/paragraph
    page_width,      # Width of the PDF page
_marker}: {e_nltk}")
                                        if line_text_    is_single_line_block, # Is this line alone in itsraw: extracted_data.append((line_text_raw, page_marker, None))
                except Exception as e_page:
                    st.error(f"Error processing PDF page {adjusted_page_num}: { block (PDF)?
    is_bold_hint,    # Is thee_page}")
                    continue
        except Exception as e_main: DOCX paragraph bold?
    is_italic_hint,  # Is the DOCX paragraph italic?
    heading_style_hint, # User selection
            st.error(f"Main PDF Extraction Error: {e_main}"); return None
        finally:
            if doc: doc.close()

    # --- DOCX Processing ---
    elif file_extension == 'docx from dropdown
    custom_regex     # User regex if provided
    ):
    """
    Checks if a line matches the heading style specified by the user.':
        try:
            document = docx.Document(io.BytesIO(file_content))
            print(f"Processing DOCX file.")
            paragraph_index = 0

            for para in document.paragraphs:
                paragraph_index += 1
                page_marker = f
    Returns chapter title text or None. Does not differentiate subchapters.
    """
    words = line_text.split()
    num_words ="Para_{paragraph_index}"
                line_text = para.text.strip()
                if not line_text or is_likely_metadata_or_footer len(words)
    is_short = 1 < num_words <(line_text): continue

                # Approximate style hints
                is_bold_hint = any(run.bold for run in para.runs if run.text.strip())
                is_italic_hint = any(run.italic 10 # General definition of short

    # --- Basic Cleanup ---
    if not line_text or num_words == 0: return None
    if is_likely_metadata_or_footer(line_text): return None

 for run in para.runs if run.text.strip())

                # Create pseudo line_dict for heuristic checker
                # NOTE: Centering and isolation    # --- Apply User Selected Logic ---

    # 1. Custom Regex (Highest Priority if provided)
    if heading_style_hint == "Custom Regex checks won't work well here
                pseudo_line_dict = {'spans': [{'text': line_text, 'font': ('italic' if is (Advanced)" and custom_regex:
        try:
            if re.match(custom_regex, line_text):
                return line_text
_italic_hint else '') + ('bold' if is_bold_hint else '')}]}

                heading_type, heading_text = check_heading_user_defined(
                    pseudo_line_dict,
                    0        except Exception as e:
            # Handle invalid regex gracefully in the main app
            print(f"Warning: Invalid custom regex: {e}")
            #, # page_width not applicable
                    False, # is_single_line_block not applicable easily
                    # Pass user criteria directly
                    require_ Fall through to other checks maybe? Or just return None? Let's return Nonebold=heading_criteria['require_bold'],
                    require_italic=heading.
            return None
        # If regex provided but doesn't match, assume_criteria['require_italic'],
                    require_title_case=heading it's not a heading by this rule
        return None

    # _criteria['require_title_case'],
                    require_all_caps2. Keyword Check
    if heading_style_hint == "Keyword (=heading_criteria['require_all_caps'],
                    require_centerede.g., 'Chapter X')":
        if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCD=False, # Cannot check reliably
                    require_isolated=False, # Cannot check reliably
                    min_words=heading_criteria['min_words'],
                    M\d]+", line_text, re.IGNORECASE) and nummax_words=heading_criteria['max_words'],
                    keyword__words < 8:
            return line_text
        return None # Only use this rule if selected

    # 3. Title Case + Shortpattern=heading_criteria['keyword_pattern']
                )

                if heading_type == 'chapter':
                    current_chapter_title_state = heading_text
                    extracted_data.append((heading_text,
    if heading_style_hint == "Title Case + Short Line":
        if line_text.istitle() and is_short and not page_marker, heading_text))
                else: # Regular text
                    try:
                        sentences = nltk.sent_tokenize(line_text)
                        for sentence in sentences:
                            sc = sentence.strip() line_text[-1] in ['.', '?', '!', ':', ',',
                            if sc: extracted_data.append((sc, page_marker, None))
                    except Exception as e_nltk: print(f" ';']:
            return line_text
        return None

    # 4Warn: NLTK err DOCX Para {page_marker}: {e. Title Case + Short + Centered (Requires line_dict for PDF)
    _nltk}"); extracted_data.append((line_text, page_marker, None))

        except Exception as e_main:
            st.error(f"Main DOCX Extraction Error: {e_main}"); returnif heading_style_hint == "Title Case + Short Line + Centered (Approx)":
        is_centered_hint = False
        if line_ None

    else:
        st.error(f"Unsupported file type: .{file_extension}")
        return None

    print(f"Extraction complete. Found {dict and 'bbox' in line_dict and page_width > 0: #len(extracted_data)} items.")
    return extracted_data

# --- END OF FILE file_processor.py ---
