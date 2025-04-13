import tiktoken

def chunk_structured_sentences(sentences_structure, tokenizer, target_tokens, overlap_sentences):
    """
    Chunks sentences provided as structured tuples, respecting chapters
    and associating chapter/subchapter titles.
    Input: [(sentence/heading_text, page_num, chapter_title, subchapter_title)]
    Output: List of dictionaries [{'chunk_text': ..., 'page_number': ..., 'chapter_title': ..., 'subchapter_title': ...}]
    """
    if not tokenizer:
        print("ERROR: Tokenizer not provided to chunker.")
        return []
    if not sentences_structure:
        print("Warning: No sentences provided to chunker.")
        return []

    chunks_data = []
    current_chunk_texts = [] # Store only the text for the current chunk
    current_chunk_pages = [] # Store page numbers for the current chunk
    current_chunk_tokens = 0
    # --- State Variables ---
    current_chapter = "Introduction / Front Matter" # Start with a default
    current_subchapter = None

    for i, (text, page_num, detected_ch_title, detected_sub_title) in enumerate(sentences_structure):

        # --- Handle Detected Headings ---
        # If it's a new CHAPTER heading (already appended as its own item):
        if detected_ch_title is not None:
            # 1. Finalize the PREVIOUS chunk if it exists
            if current_chunk_texts:
                chunk_text_joined = " ".join(current_chunk_texts).strip()
                start_page = current_chunk_pages[0] if current_chunk_pages else page_num # Page of first sentence
                if chunk_text_joined: # Ensure chunk isn't just whitespace
                    chunks_data.append({
                        "chunk_text": chunk_text_joined,
                        "page_number": start_page,
                        "chapter_title": current_chapter,
                        "subchapter_title": current_subchapter
                    })
            # 2. Update state for the *next* chunks
            current_chapter = detected_ch_title
            current_subchapter = None # Reset subchapter
            # 3. Reset current chunk - heading itself isn't part of content chunks
            current_chunk_texts = []
            current_chunk_pages = []
            current_chunk_tokens = 0
            continue # Move to next item, don't process heading as content

        # If it's a new SUBCHAPTER heading:
        if detected_sub_title is not None:
             current_subchapter = detected_sub_title
             # We'll include the subchapter text in the chunk, but don't force break yet
             # Could add break logic here if desired

        # --- Calculate tokens for the current text (sentence or subchapter heading) ---
        sentence_tokens = len(tokenizer.encode(text))

        # --- Check if adding this text exceeds target size ---
        # If the chunk is not empty AND adding the new sentence would exceed the limit
        if current_chunk_texts and (current_chunk_tokens + sentence_tokens > target_tokens):
            # 1. Finalize the current chunk
            chunk_text_joined = " ".join(current_chunk_texts).strip()
            start_page = current_chunk_pages[0] # Page of first sentence
            if chunk_text_joined:
                chunks_data.append({
                    "chunk_text": chunk_text_joined,
                    "page_number": start_page,
                    "chapter_title": current_chapter,
                    "subchapter_title": current_subchapter
                })

            # 2. --- Overlap Logic ---
            # Need the original tuples list index to backtrack for overlap
            # This requires rethinking how we store `current_chunk_sentence_tuples`
            # For simplicity, let's grab the last N *texts* and their *pages*
            overlap_start_idx = max(0, len(current_chunk_texts) - overlap_sentences)
            texts_for_overlap = current_chunk_texts[overlap_start_idx:]
            pages_for_overlap = current_chunk_pages[overlap_start_idx:]


            # 3. Start the new chunk with the overlap
            current_chunk_texts = texts_for_overlap
            current_chunk_pages = pages_for_overlap
            current_chunk_tokens = sum(len(tokenizer.encode(s)) for s in texts_for_overlap)

            # 4. Add the current sentence/subheading (that caused overflow) to the new chunk
            # Ensure it's not already in the overlap texts
            if text not in current_chunk_texts:
                current_chunk_texts.append(text)
                current_chunk_pages.append(page_num)
                current_chunk_tokens += sentence_tokens

        else:
            # --- Add current sentence/subheading to the current chunk ---
            current_chunk_texts.append(text)
            current_chunk_pages.append(page_num)
            current_chunk_tokens += sentence_tokens

    # Add the very last chunk if it has content
    if current_chunk_texts:
        chunk_text_joined = " ".join(current_chunk_texts).strip()
        start_page = current_chunk_pages[0] if current_chunk_pages else 1 # Default page
        if chunk_text_joined:
            chunks_data.append({
                "chunk_text": chunk_text_joined,
                "page_number": start_page,
                "chapter_title": current_chapter, # Use the last known chapter/subchapter
                "subchapter_title": current_subchapter
            })

    return chunks_data
