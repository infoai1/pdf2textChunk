import fitz
import re
import nltk
import streamlit as st

# --- NLTK Download Logic ---
# (Keep the download_nltk_data function as is from previous versions)
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


# --- Metadata/Footer Check ---
def is_likely_metadata_or_footer(line):
    # (Keep this function as is from previous version - you might need to tune it further)
    line = line.strip()
    if not line: return True
    cleaned_line = re.sub(r"^\W+|\W+$", "", line)
    if cleaned_line.isdigit() and line == cleaned_line and len(cleaned_line) < 4 : return True
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

# --- Simplified Heading Detection ---
def check_heading_heuristics_simple(line_text, first_span_font, is_line_mostly_styled, current_chapter_title):
    """
    Simpler heuristic focusing on keywords, style hints in font name, case, and length.
    Returns ('chapter', text), ('subchapter', text), or (None, None).
    """
    line_text = line_text.strip()
    words = line_text.split()
    num_words = len(words)

    if not line_text: return None, None

    # Style hints from font name
    is_italic_hint = "italic" in first_span_font.lower()
    is_bold_hint = "bold" in first_span_font.lower()

    # --- Rule Prioritization ---

    # 1. Explicit Chapter Keywords (High Confidence)
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", line_text, re.IGNORECASE) and num_words < 8:
        # print(f"✅ CH (Keyword): {line_text}")
        return 'chapter', line_text

    # 2. Style (Italic/Bold from font name) + Title Case + Short Length
    # This seems key for your examples like "The Creation Plan of God"
    if (is_italic_hint or is_bold_hint or is_line_mostly_styled) and line_text.istitle() and 1 < num_words < 8:
         # print(f"✅ CH (Style+Case+Len): {line_text}")
         return 'chapter', line_text

    # 3. Other Title Case Lines (Maybe Subchapters if context exists)
    if line_text.istitle() and 1 < num_words < 12:
         if not line_text[-1] in ['.', '?', '!', ':', ',', ';']: # Avoid ending punctuation
              if current_chapter_title: # If inside a chapter, guess subchapter
                   # print(f"✅ SUB (Case+Len): {line_text}")
                   return 'subchapter', line_text
              else: # Otherwise, might be an early chapter title missed by other rules
                   # print(f"✅ CH (Case+Len Fallback): {line_text}")
                   return 'chapter', line_text


    # 4. Numbered list items (Roman/Decimal) - Treat as chapter for now
    if re.match(r"^\s*[IVXLCDM]+\.?\s+.{3,}", line_text) and num_words < 10:
         # print(f"✅ CH (Roman): {line_text}")
         return 'chapter', line_text
    if re.match(r"^\s*\d+\.?\s+[A-Z].{2,}", line_text) and num_words < 8:
         # print(f"✅ CH (Decimal): {line_text}")
         return 'chapter', line_text

    return None, None # Default: Not a heading


# --- Main Extraction Function (Using get_text("blocks")) ---
def extract_sentences_with_structure(uploaded_file_content, start_skip=0, end_skip=0, start_page_offset=1):
    doc = None
    extracted_data = []
    current_chapter_title_state = None

    try:
        doc = fitz.open(stream=uploaded_file_content, filetype="pdf")
        total_pages = len(doc)

        for page_num_0based, page in enumerate(doc):
            if page_num_0based < start_skip: continue
            if page_num_0based >= total_pages - end_skip: break
            adjusted_page_num = page_num_0based - start_skip + start_page_offset

            try:
                # Using "blocks" is generally robust and gives basic line structure + font info per span
                blocks = page.get_text("blocks", sort=True) # [[x0, y0, x1, y1, "text...", block_no, block_type], ...] block_type 0 = text

                for b in blocks:
                    block_text_lines = b[4].split('\n') # Text is the 5th element (index 4)
                    # We process line by line within a block
                    for line_text in block_text_lines:
                        line_text_cleaned = line_text.strip()
                        if not line_text_cleaned or is_likely_metadata_or_footer(line_text_cleaned):
                            continue

                        # --- Get Font Info for the first span of this logical line ---
                        # This is an approximation; a line from get_text("blocks") might merge multiple formats.
                        # A more precise way needs get_text("dict") again, but let's try simple first.
                        first_span_font = "Unknown"
                        is_line_mostly_styled = False # Placeholder - can't easily get detailed flags here
                        try:
                            # We don't have easy access to spans here, so font/style check is limited
                            # Can we infer from block properties? Sometimes font info is in block dict if uniform.
                            # Let's rely more on case/length/keywords for now with get_text("blocks")
                             pass # Cannot easily get span data from "blocks" output directly here
                        except Exception:
                             pass


                        # --- Check Heading ---
                        heading_type, heading_text = check_heading_heuristics_simple(
                            line_text_cleaned,
                            first_span_font, # Pass basic font name if available
                            is_line_mostly_styled, # Pass basic style info if available
                            current_chapter_title_state
                        )

                        is_heading = heading_type is not None

                        if heading_type == 'chapter':
                            current_chapter_title_state = heading_text
                            extracted_data.append((heading_text, adjusted_page_num, heading_text, None))
                        elif heading_type == 'subchapter':
                            extracted_data.append((heading_text, adjusted_page_num, None, heading_text))
                        else: # Regular text
                            try:
                                sentences_in_line = nltk.sent_tokenize(line_text_cleaned)
                                for sentence in sentences_in_line:
                                    sentence_clean = sentence.strip()
                                    if sentence_clean:
                                        extracted_data.append((sentence_clean, adjusted_page_num, None, None))
                            except Exception as e_nltk:
                                st.warning(f"NLTK Error (Page {adjusted_page_num}): Line '{line_text_cleaned}'. Error: {e_nltk}")
                                if line_text_cleaned:
                                    extracted_data.append((line_text_cleaned, adjusted_page_num, None, None))

            except Exception as e_page:
                 st.error(f"Processing Error: Failed to process page {adjusted_page_num}. Error: {e_page}")
                 continue

        return extracted_data

    except Exception as e_main:
        st.error(f"Main Extraction Error: An unexpected error occurred: {e_main}")
        st.exception(e_main)
        return None
    finally:
        if doc: doc.close()
