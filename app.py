import streamlit as st
import pandas as pd
import fitz  # PyMuPDF
import tiktoken # For token counting

# --- Constants ---
TARGET_TOKENS = 200
OVERLAP_TOKENS = 20 # Approx 10% of 200

# --- Helper Functions ---

def get_tokenizer():
    """Initializes and returns the tokenizer."""
    try:
        return tiktoken.get_encoding("cl100k_base") # Standard for many models
    except Exception as e:
        st.error(f"Error initializing tokenizer: {e}")
        return None

def extract_text_with_pages(uploaded_file):
    """Extracts text page by page, storing page numbers."""
    doc = None
    full_text = ""
    char_to_page = [] # List to store (char_index, page_num) tuples
    current_char_index = 0

    try:
        doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        for page_num, page in enumerate(doc):
            page_text = page.get_text("text")
            if page_text: # Only process if text exists
                start_index = current_char_index
                full_text += page_text + "\n" # Add newline as separator
                end_index = len(full_text)
                # Map characters in this page's text to the page number
                for i in range(start_index, end_index):
                     # Simple mapping, could be refined
                     char_to_page.append((i, page_num + 1)) # Page numbers are 1-based
                current_char_index = end_index

        return full_text, char_to_page
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return None, None
    finally:
        if doc:
            doc.close()

def chunk_text(full_text, char_to_page_map, tokenizer):
    """Chunks text with overlap and tracks page numbers."""
    if not tokenizer:
        st.error("Tokenizer not available.")
        return []

    tokens = tokenizer.encode(full_text)
    chunks_data = []
    start_token_idx = 0

    while start_token_idx < len(tokens):
        end_token_idx = min(start_token_idx + TARGET_TOKENS, len(tokens))

        # Decode the chunk's tokens back to text
        chunk_text = tokenizer.decode(tokens[start_token_idx:end_token_idx])

        # --- Find Page Number (Simplified: page of the first token) ---
        # This requires mapping token index back to character index, which is complex.
        # SIMPLIFICATION: Get the character index corresponding to the start token.
        # This is approximate with tiktoken's direct encode/decode.
        # A more robust way involves iterating text segments and their token counts.
        # For this outline, we'll use a placeholder logic.
        # TODO: Implement accurate token_idx -> char_idx mapping if possible,
        # or use sentence-based chunking which makes page tracking easier.
        # For now, let's find the page of the *approximate* start character.
        # A better approach might be needed for high accuracy page numbers.

        # Approximate start character index based on token ratio
        # THIS IS VERY APPROXIMATE AND LIKELY NEEDS REFINEMENT
        approx_start_char_idx = int(len(full_text) * (start_token_idx / len(tokens))) if len(tokens) > 0 else 0
        start_page = 1 # Default
        # Find the first page number associated with characters near the start of the chunk
        # This needs a more robust mapping function
        try:
            # Find the closest entry in char_to_page map (this is inefficient)
            # A better approach would be to store ranges or use binary search
            relevant_pages = [p for idx, p in char_to_page_map if idx >= approx_start_char_idx]
            if relevant_pages:
                start_page = relevant_pages[0]
            elif char_to_page_map: # Fallback to last known page if calculation fails
                 start_page = char_to_page_map[-1][1]
        except Exception:
             start_page = 1 # Fallback

        chunks_data.append({
            "chunk_text": chunk_text,
            "page_number": start_page # Store the determined start page
        })

        # --- Move to the next chunk with overlap ---
        start_token_idx += TARGET_TOKENS - OVERLAP_TOKENS
        if start_token_idx >= end_token_idx: # Prevent infinite loops on short final segments
             break

    return chunks_data

# --- Streamlit App ---
st.title("PDF Rule-Based Chunker")

uploaded_file = st.file_uploader("Upload Book PDF", type="pdf")
tokenizer = get_tokenizer() # Initialize once

if uploaded_file and tokenizer:
    if st.button("Chunk PDF"):
        with st.spinner("Reading PDF and extracting text..."):
            full_text, char_to_page = extract_text_with_pages(uploaded_file)

        if full_text and char_to_page:
            st.success("PDF read successfully!")
            with st.spinner(f"Chunking text into ~{TARGET_TOKENS} token chunks with ~{OVERLAP_TOKENS} token overlap..."):
                chunk_list = chunk_text(full_text, char_to_page, tokenizer)

            if chunk_list:
                st.success(f"Text chunked into {len(chunk_list)} chunks.")
                df = pd.DataFrame(chunk_list)
                st.dataframe(df)

                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV",
                    data=csv,
                    file_name=f'{uploaded_file.name.replace(".pdf", "")}_chunks.csv',
                    mime='text/csv',
                )
            else:
                st.error("Chunking failed.")
        else:
            st.error("Could not extract text or page mapping from PDF.")
