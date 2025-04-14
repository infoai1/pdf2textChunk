import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import tiktoken
import re
import nltk
# Removed statistics import as it wasn't used in the simplified version
import time
from spellchecker import SpellChecker # Import the library

# --- NLTK Download Logic ---
@st.cache_resource
def ensure_nltk_data():
    data_ok = True
    resources = {'punkt': 'tokenizers/punkt'} # Removed punkt_tab as it wasn't fixing the core issue
    for name, path in resources.items():
        try:
            nltk.data.find(path)
        except LookupError:
            st.sidebar.info(f"Downloading NLTK data package: '{name}'...")
            try:
                nltk.download(name, quiet=True)
                st.sidebar.success(f"NLTK data '{name}' downloaded.")
            except Exception as e:
                st.sidebar.error(f"Download Error: Failed for NLTK '{name}'. Error: {e}")
                data_ok = False
        except Exception as e_find:
            st.sidebar.error(f"NLTK Find Error ({name}): {e_find}")
            data_ok = False
    if not data_ok:
        st.error("Essential NLTK data ('punkt') could not be verified/downloaded.")
    return data_ok

# --- Tokenizer Setup ---
@st.cache_resource
def get_tokenizer():
    try: return tiktoken.get_encoding("cl100k_base")
    except Exception as e: st.error(f"Error initializing tokenizer: {e}"); return None

# --- Spell Checker Setup ---
@st.cache_resource # Cache the spell checker object
def get_spell_checker():
    print("Initializing Spell Checker...") # See when this runs
    try:
        spell = SpellChecker(language='en')
        # Optional: Add known domain-specific words if needed later
        # spell.word_frequency.load_words(['Allah', 'Quran', 'Hadith', ...])
        return spell
    except Exception as e:
        st.error(f"Failed to initialize Spell Checker: {e}")
        return None

# --- PDF Utility Functions ---

def is_likely_metadata_or_footer(line):
    # (Keep as is from previous version)
    line = line.strip()
    if not line: return True
    cleaned_line = re.sub(r"^\W+|\W+$", "", line)
    if cleaned_line.isdigit() and line == cleaned_line and len(cleaned_line) < 4 : return True
    if "www." in line or ".com" in line or "@" in line or "books" in line.lower() or "global" in line.lower() or ("center" in line.lower() and "peace" in line.lower()):
         if len(line.split()) < 12: return True # Increased tolerance slightly
    if re.match(r"^\s*Page\s+\d+\s*$", line, re.IGNORECASE): return True
    if "©" in line or "copyright" in line.lower() or "first published" in line.lower() or "isbn" in line.lower(): return True
    if "printed in" in line.lower(): return True
    if any(loc in line.lower() for loc in ["nizamuddin", "new delhi", "noida", "bensalem", "byberry road"]): return True
    if len(set(line.strip())) < 4 and len(line.strip()) > 4: return True
    if line.endswith(cleaned_line) and cleaned_line.isdigit() and len(line) < 80 and len(line) > len(cleaned_line) + 2:
         if not re.search(r"[a-zA-Z]{4,}", line): return True
    return False

def check_heading_heuristics_simple(line_dict, page_width, is_single_line_block):
    """ Checks ONLY if the block is a single, short, centered line. """
    line_text = "".join(s["text"] for s in line_dict["spans"]).strip()
    words = line_text.split()
    num_words = len(words)

    if not line_text or num_words == 0: return None, None
    # Metadata check happens *before* this is called now

    # --- Tunable Parameters ---
    MAX_HEADING_WORDS = 9
    MIN_HEADING_WORDS = 1
    CENTER_TOLERANCE_RATIO = 0.18
    MIN_MARGIN_RATIO = 0.15

    # 1. Check Length & Isolation
    is_short = MIN_HEADING_WORDS <= num_words <= MAX_HEADING_WORDS
    is_isolated = is_single_line_block # Use the flag passed in

    # 2. Check Centering (Approximate)
    line_bbox = line_dict.get('bbox', None)
    is_centered_hint = False
    if line_bbox and page_width > 0:
        left_margin = line_bbox[0]; right_margin = page_width - line_bbox[2]
        if abs(left_margin - right_margin) < (page_width * CENTER_TOLERANCE_RATIO) and \
           left_margin > (page_width * MIN_MARGIN_RATIO) and \
           right_margin > (page_width * MIN_MARGIN_RATIO):
            is_centered_hint = True

    # 3. Decision: If isolated, short, and centered -> Chapter
    if is_isolated and is_short and is_centered_hint:
        if re.search("[a-zA-Z]", line_text): # Must contain letters
             # Check if it looks like Title Case (helps avoid random centered short lines)
             if line_text.istitle() or line_text.isupper():
                # print(f"✅ CH (Layout+Case): {line_text}") # Debug
                return 'chapter', line_text

    # Fallback: Explicit keywords
    if re.match(r"^\s*(CHAPTER|SECTION|PART)\s+[IVXLCDM\d]+", line_text, re.IGNORECASE) and num_words < 8:
        return 'chapter', line_text

    return None, None


def correct_text_errors(text, spell_checker):
    """Applies targeted replacements and general spell check."""
    if not text: return text

    # 1. Targeted OCR fixes (add more as you find them)
    replacements = {
        "!nd": "find",
        "te ": "The ", # Space ensures it's likely the start of sentence
        "Te ": "The "
        # Add more common errors here: e.g., "wam" -> "warn"? "bc" -> "be"?
    }
    for error, correction in replacements.items():
        text = text.replace(error, correction)

    # 2. General Spell Check (if checker is available)
    if spell_checker:
        try:
            # Split into words, handling punctuation better
            words = re.findall(r"[\w']+|[.,!?;:]", text)
            # Remove punctuation from words list for spellchecking
            words_only = [word for word in words if word.isalnum() or "'" in word]

            misspelled = spell_checker.unknown(words_only)
            corrected_words = []
            word_idx = 0
            for token in words: # Iterate original list including punctuation
                if token.isalnum() or "'" in token: # Is it a word?
                    if token in misspelled:
                        corrected_word = spell_checker.correction(token)
                        corrected_words.append(corrected_word if corrected_word else token) # Use original if no correction
                    else:
                        corrected_words.append(token) # Keep correctly spelled word
                    word_idx += 1
                else:
                    corrected_words.append(token) # Keep punctuation

            # Reconstruct sentence carefully, handling spaces around punctuation
            corrected_text = ""
            for i, word in enumerate(corrected_words):
                 corrected_text += word
                 # Add space unless it's the last word or next token is punctuation
                 if i < len(corrected_words) - 1 and \
                   (corrected_words[i+1].isalnum() or "'" in corrected_words[i+1]):
                       corrected_text += " "
            text = corrected_text

        except Exception as e:
            print(f"Spellcheck Error: {e} on text: '{text[:50]}...'")
            # Return original text if spell check fails
            pass

    return text


# --- Main Extraction Function (Simplified) ---
def extract_sentences_with_structure(uploaded_file_content, spell_checker, start_skip=0, end_skip=0, start_page_offset=1):
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
            page_width = page.rect.width

            try:
                blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT | fitz.TEXT_PRESERVE_LIGATURES)["blocks"] # Using dict

                for b_idx, b in enumerate(blocks):
                    if b['type'] == 0: # Text block
                        is_single_line_block = len(b['lines']) == 1
                        for l_idx, l in enumerate(b["lines"]):
                            line_dict = l
                            line_text_raw = "".join(s["text"] for s in l["spans"]).strip()

                            if not line_text_raw or is_likely_metadata_or_footer(line_text_raw): continue

                            # Correct potential errors BEFORE checking heuristics or tokenizing
                            line_text_corrected = correct_text_errors(line_text_raw, spell_checker)

                            heading_type, heading_text = check_heading_simple_layout(
                                line_dict, # Pass original dict for layout check
                                page_width,
                                is_single_line_block
                            )
                            # Use the *corrected* text if heading is detected
                            if heading_text: heading_text = correct_text_errors(heading_text, spell_checker)


                            is_heading = heading_type is not None

                            if heading_type == 'chapter':
                                current_chapter_title_state = heading_text
                                extracted_data.append((heading_text, adjusted_page_num, heading_text, None))
                            # NOTE: No subchapter detection in this simplified version
                            else: # Regular text
                                try:
                                    # Tokenize the *corrected* line text
                                    sentences_in_line = nltk.sent_tokenize(line_text_corrected)
                                    for sentence in sentences_in_line:
                                        sentence_clean = sentence.strip()
                                        if sentence_clean:
                                            extracted_data.append((sentence_clean, adjusted_page_num, None, None))
                                except Exception as e_nltk:
                                    st.warning(f"NLTK Error (Page {adjusted_page_num}): Line '{line_text_corrected}'. Error: {e_nltk}")
                                    # Append corrected raw line as fallback
                                    if line_text_corrected: extracted_data.append((line_text_corrected, adjusted_page_num, None, None))

            except Exception as e_page:
                 st.error(f"Processing Error: Failed to process page {adjusted_page_num}. Error: {e_page}")
                 continue
        return extracted_data
    except Exception as e_main:
        st.error(f"Main Extraction Error: {e_main}")
        st.exception(e_main)
        return None
    finally:
        if doc: doc.close()


# --- Chunker Function ---
# (Keep chunker function exactly as provided in the previous answer - v10 single file)
def chunk_structured_sentences(sentences_structure, tokenizer, target_tokens, overlap_sentences):
    if not tokenizer: print("ERROR: Tokenizer not provided."); return []
    if not sentences_structure: print("Warning: No sentences provided."); return []

    chunks_data = []
    current_chunk_texts = []
    current_chunk_pages = []
    current_chunk_tokens = 0
    current_chapter = "Unknown Chapter / Front Matter" # Initial state

    # Indices of content items (where chapter title is None)
    content_indices = [i for i, (_, _, ch, _) in enumerate(sentences_structure) if ch is None]

    def finalize_chunk():
        nonlocal chunks_data, current_chunk_texts, current_chunk_pages, current_chunk_tokens, current_chapter
        if current_chunk_texts:
            chunk_text_joined = " ".join(current_chunk_texts).strip()
            start_page = current_chunk_pages[0] if current_chunk_pages else 0
            if chunk_text_joined:
                chunks_data.append({
                    "chunk_text": chunk_text_joined,
                    "page_number": start_page,
                    "chapter_title": current_chapter,
                    "subchapter_title": "" # No subchapters detected in this simplified version
                })
            current_chunk_texts, current_chunk_pages, current_chunk_tokens = [], [], 0

    current_content_item_index = 0

    while current_content_item_index < len(content_indices):
        original_list_index = content_indices[current_content_item_index]

        # Update chapter context based on headings *before* this content item
        temp_chapter = current_chapter
        for j in range(original_list_index, -1, -1):
            _, _, ch_title_lookup, _ = sentences_structure[j]
            if ch_title_lookup is not None: temp_chapter = ch_title_lookup; break

        if temp_chapter != current_chapter:
            finalize_chunk()
            current_chapter = temp_chapter

        text, page_num, _, _ = sentences_structure[original_list_index]
        try:
            sentence_tokens = len(tokenizer.encode(text))
        except Exception as e:
            print(f"Error tokenizing text at index {original_list_index}: {e}. Skipping text.")
            current_content_item_index += 1
            continue


        # Check chunk boundary condition
        if current_chunk_texts and \
           ((current_chunk_tokens + sentence_tokens > target_tokens and sentence_tokens < target_tokens) or sentence_tokens >= target_tokens):
             finalize_chunk()

             # Overlap Logic
             overlap_start_content_idx = max(0, current_content_item_index - overlap_sentences)
             for k in range(overlap_start_content_idx, current_content_item_index):
                 overlap_original_idx = content_indices[k]
                 if overlap_original_idx < len(sentences_structure):
                     o_text, o_page, _, _ = sentences_structure[overlap_original_idx]
                     try:
                         o_tokens = len(tokenizer.encode(o_text))
                         current_chunk_texts.append(o_text)
                         current_chunk_pages.append(o_page)
                         current_chunk_tokens += o_tokens
                     except Exception as e: print(f"Error encoding overlap text: {e}")
                 else: print(f"Warning: Overlap index out of bounds.")

        # Add current text if not already added by overlap exactly
        if not current_chunk_texts or text != current_chunk_texts[-1]:
             current_chunk_texts.append(text)
             current_chunk_pages.append(page_num)
             current_chunk_tokens += sentence_tokens
        elif not current_chunk_pages or page_num != current_chunk_pages[-1]:
             current_chunk_pages.append(page_num)


        current_content_item_index += 1

    finalize_chunk()
    return chunks_data

# --- Constants ---
TARGET_TOKENS = 200
OVERLAP_SENTENCES = 2 # Approx 10-15% overlap

# --- Run Setup ---
nltk_ready = ensure_nltk_data()
tokenizer = get_tokenizer()
spell_checker = get_spell_checker() # Initialize spell checker

# --- Streamlit App UI ---
st.title("PDF Chunker v11 (Layout Heuristics + Spell Check)")
st.write("Attempts heading detection via layout, applies basic OCR/spell correction.")

uploaded_file = st.file_uploader("1. Upload Book PDF", type="pdf", key="pdf_uploader_v11")

st.sidebar.header("Processing Options")
start_skip = st.sidebar.number_input("Pages to Skip at START", min_value=0, value=0, step=1)
end_skip = st.sidebar.number_input("Pages to Skip at END", min_value=0, value=0, step=1)
start_page_offset = st.sidebar.number_input("Actual Page # of FIRST Processed Page", min_value=1, value=1, step=1)
# Add toggle for spell check
run_spell_check = st.sidebar.checkbox("Enable Spell Check (Slower)", value=True)


if not tokenizer: st.error("Tokenizer failed to load.")
elif not nltk_ready: st.error("NLTK data download/check failed.")
elif uploaded_file:
    if st.button("Process PDF", key="chunk_button_v11"):
        pdf_content = uploaded_file.getvalue()
        st.info(f"Settings: Skip {start_skip} start, {end_skip} end. Page offset {start_page_offset}. Spell Check: {'On' if run_spell_check else 'Off'}")

        # Decide which spell checker instance to pass
        active_spell_checker = spell_checker if run_spell_check else None

        with st.spinner("Step 1: Reading PDF, cleaning, correcting, & extracting structure..."):
            start_time = time.time()
            sentences_data = extract_sentences_with_structure(
                pdf_content,
                active_spell_checker, # Pass the checker instance (or None)
                start_skip=int(start_skip),
                end_skip=int(end_skip),
                start_page_offset=int(start_page_offset)
            )
            extract_time = time.time() - start_time
            st.write(f"Extraction took: {extract_time:.2f} seconds")

        if sentences_data is None: st.error("Failed to extract data.")
        elif not sentences_data: st.warning("No text content found.")
        else:
            st.success(f"Extracted {len(sentences_data)} items.")
            with st.spinner(f"Step 2: Chunking into ~{TARGET_TOKENS} token chunks..."):
                start_time = time.time()
                chunk_list = chunk_structured_sentences(
                    sentences_data, tokenizer, TARGET_TOKENS, OVERLAP_SENTENCES
                )
                chunk_time = time.time() - start_time
                st.write(f"Chunking took: {chunk_time:.2f} seconds")

            if chunk_list:
                st.success(f"Chunked into {len(chunk_list)} chunks.")
                df = pd.DataFrame(chunk_list, columns=['chunk_text', 'page_number', 'chapter_title', 'subchapter_title'])
                df['chapter_title'] = df['chapter_title'].fillna("Unknown Chapter / Front Matter")
                df['subchapter_title'] = "" # Explicitly set empty
                df = df.reset_index(drop=True)
                st.dataframe(df[['chunk_text', 'page_number', 'chapter_title']])

                csv_data = df[['chunk_text', 'page_number', 'chapter_title']].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV", data=csv_data,
                    file_name=f'{uploaded_file.name.replace(".pdf", "")}_chunks_v11_spellcheck.csv',
                    mime='text/csv', key="download_csv_v11"
                )
            else: st.error("Chunking failed.")
