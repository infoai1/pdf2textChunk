import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import tiktoken # For token counting
import re
import nltk # For sentence splitting
import time # To avoid hitting rate limits if using APIs later

# --- Download NLTK data (needed once) ---
try:
    nltk.data.find('tokenizers/punkt')
except nltk.downloader.DownloadError:
    st.info("Downloading NLTK sentence tokenizer data (punkt)...")
    nltk.download('punkt', quiet=True)
    st.success("NLTK data downloaded.")

# --- Constants ---
TARGET_TOKENS = 200
# Overlap now defined in sentences, adjust as needed
OVERLAP_SENTENCES = 2

# --- Helper Functions ---

def get_tokenizer():
    """Initializes and returns the tokenizer."""
    try:
        # Using cl100k_base, common for GPT-3.5/4
        return tiktoken.get_encoding("cl100k_base")
    except Exception as e:
        st.error(f"Error initializing tokenizer: {e}")
        return None

def is_likely_heading(sentence):
    """Basic heuristic to check if a sentence is a heading."""
    sentence = sentence.strip()
    if not sentence:
        return False
    # Short sentence?
    if len(sentence.split()) < 10:
        # Mostly uppercase? (Check ratio)
        if sum(1 for c in sentence if c.isupper()) / len(sentence.replace(" ","")) > 0.6:
             return True
        # Ends with no punctuation or specific chars often NOT in headings?
        if not sentence[-1] in ['.', '?', '!', ':', ',']:
             # Check if it resembles a title case structure (simple check)
             if sentence.istitle() and len(sentence.split()) > 1:
                 return True
    # Might be just a number (like page number)
    if sentence.isdigit():
        return False
    # Could add more rules (e.g., starts with 'Chapter', 'Section', roman numerals)
    return False

def is_likely_metadata_or_footer(line):
    """Basic heuristic to filter out metadata/footers."""
    line = line.strip()
    # Empty line
    if not line:
        return True
    # Just a page number
    if line.isdigit():
        return True
    # Common footer/header patterns (simple examples)
    if "www." in line or ".com" in line or "@" in line:
        return True
    if line.startswith("Page ") and line.replace("Page ","").isdigit():
         return True
    # Very short lines might be suspect, but keep for now unless clearly not content
    # if len(line.split()) < 3 and not is_likely_heading(line):
    #     return True
    # Check for copyright symbols or typical boilerplate starts
    if "©" in line or "Copyright" in line or "First Published" in line:
        return True
    # Add more specific rules based on your documents
    return False


def extract_sentences_with_pages(uploaded_file):
    """Extracts text, cleans it, splits into sentences, and tracks page numbers."""
    doc = None
    sentences_with_pages = [] # List to store (sentence, page_num, is_heading) tuples

    try:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        full_clean_text = ""
        for page_num, page in enumerate(doc):
            page_text = page.get_text("text")
            if not page_text:
                continue

            # Basic Cleaning - Remove likely metadata/footers line by line
            lines = page_text.split('\n')
            cleaned_lines = [line for line in lines if not is_likely_metadata_or_footer(line)]
            cleaned_page_text = "\n".join(cleaned_lines).strip()

            if not cleaned_page_text:
                continue

            # Sentence Splitting
            try:
                page_sentences = nltk.sent_tokenize(cleaned_page_text)
                for sentence in page_sentences:
                    sentence_clean = sentence.replace('\n', ' ').strip()
                    if sentence_clean: # Ignore empty strings after cleaning
                        heading_flag = is_likely_heading(sentence_clean)
                        sentences_with_pages.append((sentence_clean, page_num + 1, heading_flag))
            except Exception as e:
                st.warning(f"NLTK sentence tokenization failed on page {page_num+1}: {e}. Treating page as single block.")
                # Fallback: treat the whole cleaned page text as one 'sentence'
                heading_flag = is_likely_heading(cleaned_page_text)
                sentences_with_pages.append((cleaned_page_text, page_num + 1, heading_flag))

        return sentences_with_pages
    except Exception as e:
        st.error(f"Error reading or processing PDF: {e}")
        return None
    finally:
        if doc:
            doc.close()

def chunk_sentences(sentences_with_pages, tokenizer):
    """Chunks sentences with overlap based on target tokens."""
    if not tokenizer:
        st.error("Tokenizer not available.")
        return []
    if not sentences_with_pages:
        st.warning("No sentences extracted to chunk.")
        return []

    chunks_data = []
    current_chunk_sentences = []
    current_chunk_tokens = 0
    start_index = 0

    while start_index < len(sentences_with_pages):
        sentence, page_num, is_heading = sentences_with_pages[start_index]
        sentence_tokens = len(tokenizer.encode(sentence))

        # Start new chunk if current sentence is a heading and chunk is not empty
        if is_heading and current_chunk_sentences:
             # Finalize the previous chunk
            chunk_text = " ".join([s[0] for s in current_chunk_sentences])
            start_page = current_chunk_sentences[0][1] # Page of the first sentence
            chunks_data.append({
                "chunk_text": chunk_text,
                "page_number": start_page,
                "heading_before": is_heading # Flag if a heading *immediately* follows this chunk
            })
            # Reset for the new chunk starting *with* the heading
            current_chunk_sentences = [(sentence, page_num, is_heading)]
            current_chunk_tokens = sentence_tokens
            start_index += 1
            continue # Move to next sentence


        # If adding the current sentence exceeds the target token count
        # finalize the current chunk (unless it's empty)
        if current_chunk_tokens > 0 and (current_chunk_tokens + sentence_tokens > TARGET_TOKENS):
            chunk_text = " ".join([s[0] for s in current_chunk_sentences])
            start_page = current_chunk_sentences[0][1] # Page of the first sentence
            chunks_data.append({
                "chunk_text": chunk_text,
                "page_number": start_page,
                "heading_before": is_heading # Flag if the sentence causing overflow is a heading
            })

            # --- Overlap Logic ---
            # Take the last OVERLAP_SENTENCES from the chunk just finished
            overlap_start_idx = max(0, len(current_chunk_sentences) - OVERLAP_SENTENCES)
            sentences_for_overlap = current_chunk_sentences[overlap_start_idx:]

            # Start the new chunk with the overlap
            current_chunk_sentences = sentences_for_overlap
            current_chunk_tokens = sum(len(tokenizer.encode(s[0])) for s in sentences_for_overlap)

            # If the sentence that caused the overflow wasn't added yet, add it now
            # This check avoids adding the sentence twice if it precisely fills the overlap
            if (sentence, page_num, is_heading) not in current_chunk_sentences:
                 current_chunk_sentences.append((sentence, page_num, is_heading))
                 current_chunk_tokens += sentence_tokens

        else:
            # Add the current sentence to the chunk
            current_chunk_sentences.append((sentence, page_num, is_heading))
            current_chunk_tokens += sentence_tokens

        # Move to the next sentence
        start_index += 1

    # Add the last remaining chunk if it's not empty
    if current_chunk_sentences:
        chunk_text = " ".join([s[0] for s in current_chunk_sentences])
        start_page = current_chunk_sentences[0][1]
        chunks_data.append({
            "chunk_text": chunk_text,
            "page_number": start_page,
            "heading_before": False # No heading follows the very last chunk
        })

    return chunks_data


# --- Streamlit App ---
st.title("PDF Sentence Chunker (Improved)")

uploaded_file = st.file_uploader("Upload Book PDF", type="pdf")
tokenizer = get_tokenizer() # Initialize once

if uploaded_file and tokenizer:
    if st.button("Chunk PDF"):
        with st.spinner("Reading PDF, cleaning, and extracting sentences..."):
            sentences_data = extract_sentences_with_pages(uploaded_file)

        if sentences_data:
            st.success(f"Extracted {len(sentences_data)} sentences.")
            with st.spinner(f"Chunking sentences into ~{TARGET_TOKENS} token chunks with ~{OVERLAP_SENTENCES} sentence overlap..."):
                chunk_list = chunk_sentences(sentences_data, tokenizer)

            if chunk_list:
                st.success(f"Text chunked into {len(chunk_list)} chunks.")
                # Optionally remove the heading_before column if not needed in final CSV
                # df = pd.DataFrame(chunk_list, columns=['chunk_text', 'page_number'])
                df = pd.DataFrame(chunk_list)
                st.dataframe(df)

                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV",
                    data=csv,
                    file_name=f'{uploaded_file.name.replace(".pdf", "")}_sentence_chunks.csv',
                    mime='text/csv',
                )
            else:
                st.error("Chunking failed or resulted in no chunks.")
        else:
            st.error("Could not extract sentences from PDF.")
