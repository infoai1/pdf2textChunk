import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import tiktoken
import re
import nltk
import time

# --- Download NLTK data (needed once) ---
try:
    nltk.data.find('tokenizers/punkt')
except nltk.downloader.DownloadError:
    st.info("Downloading NLTK sentence tokenizer data (punkt)...")
    nltk.download('punkt', quiet=True)
    st.success("NLTK data downloaded.")

# --- Constants ---
TARGET_TOKENS = 200
OVERLAP_SENTENCES = 2 # Number of sentences to overlap

# --- Helper Functions ---

def get_tokenizer():
    """Initializes and returns the tokenizer."""
    try:
        return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        st.error(f"Error initializing tokenizer: {e}")
        return None

# --- Heuristics for Structure Detection (NEEDS TUNING) ---
def is_likely_chapter_heading(line):
    """Guess if a line is a chapter heading."""
    line = line.strip()
    if not line: return None
    # Simple pattern check (adapt to your books)
    if re.match(r"^\s*CHAPTER\s+\d+", line, re.IGNORECASE): return line
    if re.match(r"^\s*[IVXLCDM]+\.\s+", line): return line # Roman numerals
    if re.match(r"^\s*\d+\.\s+", line) and len(line.split()) < 7: return line # Numbered list start, short
    # Less reliable: All caps, short line
    if line.isupper() and len(line.split()) < 7 and len(line) > 3: return line
    return None

def is_likely_subchapter_heading(line, current_chapter):
    """Guess if a line is a subchapter heading (more difficult)."""
    line = line.strip()
    if not line: return None
    # Avoid detecting chapter headings again
    if is_likely_chapter_heading(line): return None
    # Title case, relatively short, not ending in typical punctuation
    if (line.istitle() or (sum(1 for c in line if c.isupper()) / len(line.replace(" ","")) > 0.3 and len(line.split())>1) ) \
       and len(line.split()) < 10 \
       and len(line) > 3 \
       and not line[-1] in ['.', '?', '!', ':', ','] \
       and current_chapter is not None: # Only detect subchapters *within* a chapter
           return line
    return None

def is_likely_metadata_or_footer(line):
    """Basic heuristic to filter out metadata/footers/page numbers."""
    line = line.strip()
    # Empty line
    if not line: return True
    # Just a page number (potentially surrounded by --- or similar)
    cleaned_line = re.sub(r"^[\s\-—_]+|[\s\-—_]+$", "", line) # Remove surrounding dashes/spaces
    if cleaned_line.isdigit(): return True
    # Common footer/header patterns
    if "www." in line or ".com" in line or "@" in line or "goodwordbooks" in line or "cpsglobal" in line: return True
    if re.match(r"^\s*Page\s+\d+\s*$", line, re.IGNORECASE): return True
    # Check for copyright symbols or typical boilerplate starts
    if "©" in line or "Copyright" in line or re.match(r"^\s*First Published", line): return True
    if "ISBN" in line: return True
    # Lines that are just decorative separators
    if len(set(line.strip())) < 3 and len(line.strip()) > 3: # e.g., "------" or "****"
         return True
    # Lines that seem like TOC entries (needs refinement)
    if re.match(r"^[.\s]*\d+$", line.split()[-1]) and len(line) < 80: # Ends in number, possibly with dots
        # Check if it doesn't look like a normal sentence ending in a number
        if not re.search(r"[a-zA-Z]{3,}", line): # Doesn't contain longer words
             return True
    return False

def extract_sentences_with_structure(uploaded_file):
    """Extracts text, cleans, splits sentences, tracks pages & detects headings."""
    doc = None
    # List stores: (sentence, page_num, chapter_title_on_this_line, subchapter_title_on_this_line)
    sentences_structure = []
    current_chapter_title_state = None # Keep track of the current chapter

    try:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        for page_num_0based, page in enumerate(doc):
            page_num = page_num_0based + 1
            page_text = page.get_text("text")
            if not page_text: continue

            lines = page_text.split('\n')
            temp_page_sentences = []

            for line in lines:
                if is_likely_metadata_or_footer(line):
                    continue # Skip this line

                line_clean = line.strip()
                if not line_clean: continue

                # --- Heading Detection ---
                chapter_heading = is_likely_chapter_heading(line_clean)
                subchapter_heading = None
                if not chapter_heading: # Only check for subchapter if it's not a chapter
                    subchapter_heading = is_likely_subchapter_heading(line_clean, current_chapter_title_state)

                if chapter_heading:
                    current_chapter_title_state = chapter_heading # Update current chapter
                    temp_page_sentences.append((chapter_heading, page_num, chapter_heading, None))
                elif subchapter_heading:
                     temp_page_sentences.append((subchapter_heading, page_num, None, subchapter_heading))
                else:
                    # --- Sentence Splitting for non-headings ---
                    try:
                        sentences_in_line = nltk.sent_tokenize(line_clean)
                        for sentence in sentences_in_line:
                            sentence_clean_again = sentence.strip()
                            if sentence_clean_again:
                                temp_page_sentences.append((sentence_clean_again, page_num, None, None))
                    except Exception as e:
                        # Fallback for tokenization error on a specific line
                        st.warning(f"NLTK failed on line: '{line_clean}' on page {page_num}. Treating as single sentence. Error: {e}")
                        if line_clean: # Ensure it's not empty
                           temp_page_sentences.append((line_clean, page_num, None, None))

            sentences_structure.extend(temp_page_sentences)

        return sentences_structure
    except Exception as e:
        st.error(f"Error reading or processing PDF: {e}")
        return None
    finally:
        if doc: doc.close()

def chunk_structured_sentences(sentences_structure, tokenizer):
    """Chunks sentences, respecting chapters and associating titles."""
    if not tokenizer: st.error("Tokenizer not available."); return []
    if not sentences_structure: st.warning("No sentences extracted."); return []

    chunks_data = []
    current_chunk_sentence_tuples = [] # Stores (sentence, page, ch_head, sub_head)
    current_chunk_tokens = 0
    current_chapter = "Unknown" # Default/Initial
    current_subchapter = None # Optional, reset with chapter

    for i, (sentence, page_num, ch_title, sub_title) in enumerate(sentences_structure):

        # --- Handle Detected Headings ---
        is_chapter_heading = ch_title is not None
        is_subchapter_heading = sub_title is not None

        # If it's a new CHAPTER heading:
        if is_chapter_heading:
            # 1. Finalize the PREVIOUS chunk if it exists
            if current_chunk_sentence_tuples:
                chunk_text = " ".join([s[0] for s in current_chunk_sentence_tuples])
                start_page = current_chunk_sentence_tuples[0][1]
                chunks_data.append({
                    "chunk_text": chunk_text,
                    "page_number": start_page,
                    "chapter_title": current_chapter,
                    "subchapter_title": current_subchapter
                })
            # 2. Update state for the *next* chunks
            current_chapter = ch_title
            current_subchapter = None # Reset subchapter when chapter changes
            # 3. Reset current chunk variables - the heading itself doesn't start the *content* chunk
            current_chunk_sentence_tuples = []
            current_chunk_tokens = 0
            continue # Skip adding the heading itself as the start of a content chunk

        # If it's a new SUBCHAPTER heading:
        if is_subchapter_heading:
            # Update state for the *next* sentences/chunks
            current_subchapter = sub_title
            # We *don't* force a chunk break for subchapters here, but you could add it
            # For now, just record it. The subchapter title *will* be part of the chunk.


        # --- Calculate tokens for the current sentence ---
        sentence_tokens = len(tokenizer.encode(sentence))

        # --- Check if adding this sentence exceeds target size ---
        if current_chunk_tokens > 0 and (current_chunk_tokens + sentence_tokens > TARGET_TOKENS):
            # 1. Finalize the current chunk
            chunk_text = " ".join([s[0] for s in current_chunk_sentence_tuples])
            start_page = current_chunk_sentence_tuples[0][1]
            chunks_data.append({
                "chunk_text": chunk_text,
                "page_number": start_page,
                "chapter_title": current_chapter,
                "subchapter_title": current_subchapter
            })

            # 2. --- Overlap Logic ---
            overlap_start_idx = max(0, len(current_chunk_sentence_tuples) - OVERLAP_SENTENCES)
            sentences_for_overlap = current_chunk_sentence_tuples[overlap_start_idx:]

            # 3. Start the new chunk with the overlap
            current_chunk_sentence_tuples = sentences_for_overlap
            current_chunk_tokens = sum(len(tokenizer.encode(s[0])) for s in sentences_for_overlap)

            # 4. Add the current sentence (that caused the overflow) to the new chunk
            # Check if it wasn't already part of the overlap
            if (sentence, page_num, ch_title, sub_title) not in current_chunk_sentence_tuples:
                current_chunk_sentence_tuples.append((sentence, page_num, ch_title, sub_title))
                current_chunk_tokens += sentence_tokens

        else:
            # --- Add current sentence to the current chunk ---
            current_chunk_sentence_tuples.append((sentence, page_num, ch_title, sub_title))
            current_chunk_tokens += sentence_tokens


    # Add the very last chunk if it has content
    if current_chunk_sentence_tuples:
        chunk_text = " ".join([s[0] for s in current_chunk_sentence_tuples])
        start_page = current_chunk_sentence_tuples[0][1]
        chunks_data.append({
            "chunk_text": chunk_text,
            "page_number": start_page,
            "chapter_title": current_chapter, # Use the last known chapter/subchapter
            "subchapter_title": current_subchapter
        })

    return chunks_data

# --- Streamlit App ---
st.title("PDF Structured Chunker")
st.write("Upload a PDF. The app will attempt to clean it, identify chapters/subchapters (heuristically), and create overlapping sentence-based chunks, preventing chunks from spanning across detected chapter breaks.")

uploaded_file = st.file_uploader("Upload Book PDF", type="pdf", key="pdf_uploader")
tokenizer = get_tokenizer()

if uploaded_file and tokenizer:
    if st.button("Chunk PDF with Structure", key="chunk_button"):
        with st.spinner("Reading PDF, cleaning, and extracting structured sentences..."):
            sentences_data = extract_sentences_with_structure(uploaded_file)

        if sentences_data:
            st.success(f"Extracted {len(sentences_data)} potential sentences/headings.")
            with st.spinner(f"Chunking sentences into ~{TARGET_TOKENS} token chunks..."):
                chunk_list = chunk_structured_sentences(sentences_data, tokenizer)

            if chunk_list:
                st.success(f"Text chunked into {len(chunk_list)} chunks.")
                df = pd.DataFrame(chunk_list)
                st.dataframe(df)

                csv_data = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV",
                    data=csv_data,
                    file_name=f'{uploaded_file.name.replace(".pdf", "")}_structured_chunks.csv',
                    mime='text/csv',
                    key="download_csv"
                )
            else:
                st.error("Chunking failed or resulted in no chunks.")
        else:
            st.error("Could not extract structured sentences from PDF.")
