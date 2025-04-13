import tiktoken

def chunk_structured_sentences(sentences_structure, tokenizer, target_tokens, overlap_sentences):
    """
    Chunks sentences provided as structured tuples, respecting chapters
    and associating chapter/subchapter titles.
    Input: List of (text, page_num, chapter_title, subchapter_title) tuples.
    Output: List of dictionaries.
    """
    if not tokenizer: print("ERROR: Tokenizer not provided."); return []
    if not sentences_structure: print("Warning: No sentences provided."); return []

    chunks_data = []
    current_chunk_texts = [] # Stores only the actual text content for the chunk
    current_chunk_pages = [] # Stores page numbers for context if needed
    current_chunk_tokens = 0
    # --- State Variables ---
    current_chapter = "Unknown Chapter / Front Matter" # Default chapter name
    current_subchapter = None

    # --- Helper function to finalize a chunk ---
    def finalize_chunk():
        nonlocal chunks_data, current_chunk_texts, current_chunk_pages, current_chunk_tokens, current_chapter, current_subchapter
        if current_chunk_texts:
            chunk_text_joined = " ".join(current_chunk_texts).strip()
            start_page = current_chunk_pages[0] if current_chunk_pages else 0
            if chunk_text_joined: # Avoid empty chunks
                chunks_data.append({
                    "chunk_text": chunk_text_joined,
                    "page_number": start_page,
                    "chapter_title": current_chapter,
                    "subchapter_title": current_subchapter
                })
            # Reset for next chunk (important!)
            current_chunk_texts = []
            current_chunk_pages = []
            current_chunk_tokens = 0

    # --- Iterate through the structured data ---
    for i, (text, page_num, detected_ch_title, detected_sub_title) in enumerate(sentences_structure):

        # --- Handle Detected Headings ---
        if detected_ch_title is not None:
            # Finish the previous chunk *before* updating chapter state
            finalize_chunk()
            # Update chapter state and reset subchapter
            current_chapter = detected_ch_title
            current_subchapter = None
            # print(f"--- CH DETECTED: {current_chapter} ---") # Debug
            continue # Skip adding heading text to content chunks

        if detected_sub_title is not None:
             # Option 1: Finish previous chunk and start new one (like chapters)
             # finalize_chunk()
             # Option 2: Just update state and include heading in text (current implementation)
            current_subchapter = detected_sub_title
            # print(f"--- SUB DETECTED: {current_subchapter} ---") # Debug
            # Fall through to treat it like normal text for chunking purposes

        # --- Regular text processing ---
        sentence_tokens = len(tokenizer.encode(text))

        # --- Check if adding this text exceeds target size ---
        # If chunk has content AND adding new text exceeds limit OR if text is too long itself
        if current_chunk_texts and (current_chunk_tokens + sentence_tokens > target_tokens):
            # 1. Finalize the current chunk
            finalize_chunk()

            # 2. --- Overlap Logic ---
            # Find the index in the original list corresponding to the start of the overlap
            # This is tricky because we skipped headings. We need to search backward in the original list.
            overlap_start_original_index = -1
            sentences_counted_back = 0
            for j in range(i - 1, -1, -1): # Iterate backwards from the sentence *before* the current one
                prev_text, _, prev_ch, prev_sub = sentences_structure[j]
                # Only count non-heading text towards overlap sentences
                if prev_ch is None and prev_sub is None:
                    sentences_counted_back += 1
                    if sentences_counted_back >= overlap_sentences:
                         overlap_start_original_index = j
                         break
            if overlap_start_original_index == -1: # If not enough sentences for overlap
                overlap_start_original_index = max(0, i - overlap_sentences) # Fallback based on index

            # 3. Start the new chunk with the overlap content
            # Iterate from the calculated overlap start index up to (but not including) current index `i`
            for k in range(overlap_start_original_index, i):
                o_text, o_page, o_ch, o_sub = sentences_structure[k]
                # Add only actual text (not chapter headings) to the new chunk's overlap
                if o_ch is None: # Subchapter headings *are* included here currently
                    o_tokens = len(tokenizer.encode(o_text))
                    current_chunk_texts.append(o_text)
                    current_chunk_pages.append(o_page)
                    current_chunk_tokens += o_tokens


            # 4. Add the current sentence/subheading (that caused overflow) to the new chunk
            current_chunk_texts.append(text)
            current_chunk_pages.append(page_num)
            current_chunk_tokens += sentence_tokens

        else:
            # --- Add current sentence/subheading to the current chunk ---
            current_chunk_texts.append(text)
            current_chunk_pages.append(page_num)
            current_chunk_tokens += sentence_tokens

    # Add the very last chunk if it has content
    finalize_chunk()

    return chunks_data
