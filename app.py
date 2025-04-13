import streamlit as st
import pandas as pd
import tik _ = sentences_structure[overlap_original_idx] # Overlap text doesn't need heading infotoken
import time

from pdf_utils import extract_sentences_with_structure, download_nltk_
                     o_tokens = len(tokenizer.encode(o_text))
                     current_chunk_texts.append(o_text)
                     current_chunkdata
from chunker import chunk_structured_sentences

# --- Constants ---
TARGET_TOKENS =_pages.append(o_page)
                     current_chunk_tokens 200
OVERLAP_SENTENCES = 2 # <--- Set += o_tokens
                 else:
                     print(f"Warning: Overlap index {overlap_ to 2 for ~10-15% overlap (approx 20-4original_idx} out of bounds.")
            # --- End Overlap Logic ---

        0 tokens)

# --- NLTK Setup ---
st.sidebar.title("# Add current text to the chunk (unless it was just used for overlap)
        current_Setup Status")
punkt_ready = download_nltk_data('punkt', 'tokenchunk_texts.append(text)
        current_chunk_pages.izers/punkt')
# punkt_tab not needed usually
nltk_ready = punkt_ready

# --- Tokenizer Setup ---
@st.cache_resource
def get_tokenizer():
    try: return tiktoken.get_encoding("cl100k_base")
append(page_num)
        current_chunk_tokens += sentence_tokens

        current_content_item_index += 1 # Move to the next content item

    finalize_chunk() # Add the last chunk

    return chunks_data
    except Exception as e: st.error(f"Error initializing tokenizer: {e}"); return None

# --- Streamlit App UI ---
st.title("PDF Structured Chunker v8```

---

**3. `app.py` (Update Overlap Constant (Style/Case Heuristics)")
st.write("Upload PDF, specify and Output)**

```python
import streamlit as st
import pandas as pd
import tiktoken
import time

from pdf_utils import extract_sentences_with_structure, download_nltk_data
from chunker import chunk_structured_sentences

# --- Constants ---
TARGET_TOKENS = skips/offset. Attempts heading detection based on style, case, length.")

uploaded_file = st. 200
OVERLAP_SENTENCES = 2 # Use 2 sentences for ~10file_uploader("1. Upload Book PDF", type="pdf", key="pdf_uploader_v8")

st.sidebar.header("Processing Options-15% overlap approx

# --- NLTK Setup ---
st.sidebar.title("")
start_skip = st.sidebar.number_input("Pages toSetup Status")
punkt_ready = download_nltk_data('punkt', 'tokenizers/ Skip at START", min_value=0, value=0, step=punkt')
nltk_ready = punkt_ready

# --- Tokenizer Setup ---
@st.cache1, help="e.g., Cover, Title, Copyright pages.")
end_skip = st.sidebar.number_input("Pages to Skip at END", min_value=0, value=0, step=1, help_resource
def get_tokenizer():
    try:
        return tiktoken.get_encoding("="e.g., Index, Ads pages.")
start_page_offsetcl100k_base")
    except Exception as e:
        st.error( = st.sidebar.number_input("Actual Page # of FIRST Processedf"Error initializing tokenizer: {e}")
        return None

# --- Streamlit App UI ---
 Page", min_value=1, value=1, step=1,st.title("PDF Layout Chunker v8 (Simplified)")
st.write("Upload PDF, specify skips/offset. Attempts heading detection based on layout cues help="Page number printed on the first content page.")

tokenizer = get_tokenizer()

if not tokenizer: st.error("Tokenizer could not be loaded.")
elif not nltk_ready: st.error("NLTK 'punkt' data package could (centered, short, isolated line).")

uploaded_file = st.file_ not be verified/downloaded.")
elif uploaded_file:
    if st.button("Process PDF", key="chunk_button_v8"):
        pdf_content = uploaded_file.getvalue()
        st.info(fuploader("1. Upload Book PDF", type="pdf", key="pdf_"Settings: Skip first {start_skip}, Skip last {end_skipuploader_v8")

st.sidebar.header("Processing Options")
}, Start numbering from page {start_page_offset}")

        with st.spinner("Step 1: Reading PDF and extracting structure..."):
            start_time = time.time()
            sentences_data = extract_sentences_with_structure(
                pdf_content,
                start_skip=int(start_skip), end_skip=intstart_skip = st.sidebar.number_input("Pages to Skip at START", min_value=0, value=0, step=1,(end_skip), start_page_offset=int(start_page_offset)
            ) help="e.g., Cover, Title, Copyright pages.")
end_skip = st.sidebar.number_input("Pages to Skip at END", min_value=0, value
            extract_time = time.time() - start_time
            st.write(f"Extraction took: {extract_time:.2f} seconds")

        if sentences_data is None: st.error("Failed to extract data. Check PDF or=0, step=1, help="e.g., Index, Ads pages.")
start_page_offset = st.sidebar.number_input("Actual Page # adjust skip settings.")
        elif not sentences_data: st.warning("No text content found after cleaning/skipping.")
        else:
            st.success(f"Extracted {len(sentences_data)} potential sentences/headings.")
            with st. of FIRST Processed Page", min_value=1, value=1, step=1, help="Page number printed on the first content page.")

tokenizerspinner(f"Step 2: Chunking sentences into ~{TARGET_ = get_tokenizer()

if not tokenizer:
    st.error("Tokenizer could not be loaded.")
elif not nltk_ready:
     st.errorTOKENS} token chunks..."):
                start_time = time.time()
                chunk_list = chunk_structured_sentences(
                    sentences_data, tokenizer, TARGET("NLTK 'punkt' data package could not be verified/downloaded.")
elif uploaded__TOKENS, OVERLAP_SENTENCES
                )
                chunk_time = time.timefile:
    if st.button("Process PDF", key="chunk_button_v8"):
        () - start_time
                st.write(f"Chunking took: {chunk_time:.pdf_content = uploaded_file.getvalue()
        st.info(f"Settings: Skip first {start_skip}, Skip last {end_skip}, Start2f} seconds")

            if chunk_list:
                st. numbering from page {start_page_offset}")

        with st.spinner("Step 1: Reading PDF and extracting structure..."):
            start_time = timesuccess(f"Text chunked into {len(chunk_list)} chunks.")
                df.time()
            sentences_data = extract_sentences_with_structure(
                pdf_content,
                start_skip=int(start_skip),
                end_skip=int(end_skip),
 = pd.DataFrame(chunk_list, columns=['chunk_text', 'page_number', 'chapter_title', 'subchapter_title'])
                df['chapter_title                start_page_offset=int(start_page_offset)
            )
            extract_time = time.time() - start_time
            st.write'] = df['chapter_title'].fillna("Unknown Chapter / Front Matter")(f"Extraction took: {extract_time:.2f} seconds")

        if sentences_data is None:
            st.error("Failed
                df['subchapter_title'] = df['subchapter_title'].fillna("")
                df = df.reset_index(drop=True)
                st.dataframe(df)
                csv_data = df.to_csv to extract data. Check PDF or adjust skip settings.")
        elif not sentences_data:
             st.warning("No text content found after cleaning/skipping.")
        else:
            st.success(f"Extracted {len(sentences_data)} potential sentences/headings.")
            with st.spinner((index=False).encode('utf-8')
                st.download_button(
                    label="Download data as CSV",
                    data=f"Step 2: Chunking sentences into ~{TARGET_TOKENS} token chunks..."):
                start_time = time.time()
                chunk_listcsv_data,
                    file_name=f'{uploaded_file.name.replace(".pdf", "")}_style_chunks_v8.csv',
                    mime='text/csv',
                    key="download_csv_v8"
                )
             = chunk_structured_sentences(
                    sentences_data,
                    tokenizer,
                    TARGET_TOKENS,
                    OVERLAP_SENTENCES #else: st.error("Chunking failed or resulted in no chunks.")
 Pass overlap value
                )
                chunk_time = time.time() - start_time
                st.write(f"Chunking took: {```

**Summary of Logic in `pdf_utils.py`:**

*chunk_time:.2f} seconds")

            if chunk_list:
                st.success(f"Text chunked into {len(chunk   It primarily looks for lines that are **styled (italic/bold)** AND **Title Case** AND **short** (2-9 words) AND don_list)} chunks.")
                # Output columns (subchapter will be None or empty)
                df = pd.DataFrame(chunk_list, columns=['chunk_text', 'page_number', 'chapter_title', 'subchapter't end with punctuation. These are considered high-confidence **Chapter** titles based_title'])
                df['chapter_title'] = df['chapter_ on your examples.
*   As a fallback, it considers lines that are **Title Case** AND **short** (2-11 words) AND lack ending punctuation. Iftitle'].fillna("Unknown Chapter / Front Matter")
                df['subchapter a chapter title has already been seen (`current_chapter_title` is set_title'] = "" # Ensure empty string for this simplified version

                df = df.reset_index(drop=True)
                st.dataframe(df[['chunk_text', 'page_number', 'chapter_title']]) # Display relevant), these are guessed as **Subchapters**. If no chapter context exists, it guesses columns

                csv_data = df[['chunk_text', 'page_number', 'chapter_title']].to_csv(index=False).encode('utf-8') # Export relevant columns
                st.download_button(
                    label="Download **Chapter**.
*   Explicit keywords like "CHAPTER X" are still checked data as CSV",
                    data=csv_data,
                    file_name=f'{uploaded_file.name.replace(".pdf", "")}_layout_chunks_v first.
*   Font *size* difference and centering are *ignored* in this version to8.csv',
                    mime='text/csv',
                    key=" simplify and avoid potential errors from inconsistent PDF data.

Run this version. Itdownload_csv_v8"
                )
            else:
                st.error("Chunking failed or resulted in no chunks.")
