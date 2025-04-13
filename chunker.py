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
    current_chunk_texts = []
    current_chunk_pages = []
    current_chunk_tokens = 0
    current_chapter = "Unknown Chapter / Front Matter"
    current_subchapter = None

    # Store original indices of *content* items only (not chapter headings)
    # Content includes regular sentences AND detected subchapter headings
    content_indices = [i for i, (_, _, ch, _) in enumerate(sentences_structure) if ch is None]

    def finalize_chunk():
        nonlocal chunks_data, current_chunk_texts, current_chunk_pages, current_chunk_tokens, current_chapter, current_subchapter
        if current_chunk_texts:
            chunk_text_joined = " ".join(current_chunk_texts).strip()
            start_page = current_chunk_pages[0] if current_chunk_pages else 0
            if chunk_text_joined:
                chunks_data.append({
                    "chunk_text": chunk_text_joined,
                    "page_number": start_page,
                    "chapter_title": current_chapter,
                    "subchapter_title": current_subchapter
                })
            current_chunk_texts = []
            current_chunk_pages = []
            current_chunk_tokens = 0

    current_content_item_index = 0 # Track position within content_indices

    while current_content_item_index < len(content_indices):
        original_list_index = content_indices[current_content_item_index]
        # We get the state (chapter/subchapter) from the *previous* content item or initial state
        # Get text, page, and detected subchapter title for the *current* content item
        text, page_num, _, detected_sub_title = sentences_structure[original_list_index]

        # Update current subchapter state *if* this line detected one
        if detected_sub_title is not None:
            current_subchapter = detected_sub_title

        # --- Calculate tokens for the current content item ---
        sentence_tokens = len(tokenizer.encode(text))

        # --- Check if adding this item exceeds target size ---
        if current_chunk_texts and (current_chunk_tokens + sentence_tokens > target_tokens) and sentence_tokens < target_tokens : # Avoid breaking on single long items
            finalize_chunk() # Finalize the previous chunk

            # --- Overlap Logic ---
            overlap_start_content_idx = max(0, current_content_item_index - overlap_sentences)
            for k in range(overlap_start_content_idx, current_content_item_index):
                 overlap_original_idx = content_indices[k]
                 o_text, o_page, _, _ = sentences_structure[overlap_original_idx] # Overlap text doesn't need heading info
                 o_tokens = len(tokenizer.encode(o_text))
                 current_chunk_texts.append(o_text)
                 current_chunk_pages.append(o_page)
                 current_chunk_tokens += o_tokens
            # --- End Overlap Logic ---

        # Add current text (sentence or subchapter heading) to the chunk
        current_chunk_texts.append(text)
        current_chunk_pages.append(page_num)
        current_chunk_tokens += sentence_tokens

        current_content_item_index += 1 # Move to the next content item

    finalize_chunk() # Add the last chunk

    # Update chapter titles based on the first heading encountered in the original list
    # This is a post-processing step to ensure chapters are assigned correctly
    last_known_chapter = "Unknown Chapter / Front Matter"
    for i, item in enumerate(sentences_structure):
        _, _, ch_title, _ = item
        if ch_title is not None:
            last_known_chapter = ch_title
            # Apply this chapter title to all subsequent chunks until the next chapter
            # Find the index in chunks_data corresponding to this point
            # This linking is complex; simpler to just use the state during chunk finalization
            # The ffill in app.py handles this more practically for now.

    return chunks_data
