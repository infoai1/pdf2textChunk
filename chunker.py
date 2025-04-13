import tiktoken

def chunk_structured_sentences(sentences_structure, tokenizer, target_tokens, overlap_sentences):
    """
    Chunks sentences/headings, assigns last known chapter title.
    Assumes sentences_structure provides chapter titles but not subchapters.
    Input: List of (text, page_num, chapter_title_if_heading, None) tuples.
    Output: List of dictionaries [{'chunk_text': ..., 'page_number': ..., 'chapter_title': ..., 'subchapter_title': None}]
    """
    if not tokenizer: print("ERROR: Tokenizer not provided."); return []
    if not sentences_structure: print("Warning: No sentences provided."); return []

    chunks_data = []
    current_chunk_texts = []
    current_chunk_pages = []
    current_chunk_tokens = 0
    current_chapter = "Unknown Chapter / Front Matter" # Initial state

    # Store original indices of *content* items only (not chapter headings)
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
                    "subchapter_title": None # Set subchapter to None explicitly
                })
            # Reset for next chunk
            current_chunk_texts = []
            current_chunk_pages = []
            current_chunk_tokens = 0

    current_content_item_index = 0 # Track position within content_indices

    while current_content_item_index < len(content_indices):
        original_list_index = content_indices[current_content_item_index]

        # Find the most recent chapter heading *before or at* this original index
        temp_chapter = current_chapter
        for j in range(original_list_index, -1, -1):
            _, _, ch_title_lookup, _ = sentences_structure[j]
            if ch_title_lookup is not None:
                temp_chapter = ch_title_lookup
                break
        # If the chapter context changed *before* this content item started
        if temp_chapter != current_chapter:
             finalize_chunk() # Finalize the chunk belonging to the old chapter
             current_chapter = temp_chapter # Update to the new chapter

        # Now process the actual content item
        text, page_num, _, _ = sentences_structure[original_list_index]

        sentence_tokens = len(tokenizer.encode(text))

        # Check for chunk boundary
        # Finalize if chunk has text AND (adding sentence exceeds target OR sentence itself is huge)
        if current_chunk_texts and \
           ((current_chunk_tokens + sentence_tokens > target_tokens and sentence_tokens < target_tokens) or sentence_tokens >= target_tokens):
            finalize_chunk()

                    # --- Overlap Logic ---
        overlap_start_content_idx = max(0, current_content_item_index - overlap_sentences)
        for k in range(overlap_start_content_idx, current_content_item_index):
             overlap_original_idx = content_indices[k]
             # Ensure index is valid before accessing
             if overlap_original_idx < len(sentences_structure):
                 o_text, o_page, _, _ = sentences_structure[overlap_original_idx]
                 # --> Check indentation of this block carefully <--
                 o_tokens = len(tokenizer.encode(o_text))
                 current_chunk_texts.append(o_text)
                 current_chunk_pages.append(o_page)
                 current_chunk_tokens += o_tokens
                 # --> End of block to check <--
             else:
                 print(f"Warning: Overlap index {overlap_original_idx} out of bounds.")
        # --- End Overlap Logic ---

        # Add current text to the chunk (unless it was just used for overlap)
        # Need to ensure the current text isn't identical to the last appended text if overlap included it.
        # A simpler check: just add it. Overlap might slightly duplicate the start of the chunk.
        current_chunk_texts.append(text)
        current_chunk_pages.append(page_num)
        current_chunk_tokens += sentence_tokens


        current_content_item_index += 1 # Move to the next content item

    finalize_chunk() # Add the last chunk

    return chunks_data
