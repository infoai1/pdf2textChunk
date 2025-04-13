import tiktoken

def chunk_structured_sentences(sentences_structure, tokenizer, target_tokens, overlap_sentences):
    """
    Chunks sentences/headings, assigns last known chapter title.
    Input: List of (text, page_num, chapter_title_if_heading, None) tuples.
           Subchapter title is ignored/not produced by the simplified pdf_utils.
    Output: List of dictionaries.
    """
    if not tokenizer: print("ERROR: Tokenizer not provided."); return []
    if not sentences_structure: print("Warning: No sentences provided."); return []

    chunks_data = []
    current_chunk_texts = []
    current_chunk_pages = []
    current_chunk_tokens = 0
    current_chapter = "Unknown Chapter / Front Matter" # Initial state

    # Store original indices of *content* items (non-chapter headings)
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
                    "subchapter_title": None # Subchapters not detected by this simple version
                })
            current_chunk_texts = []
            current_chunk_pages = []
            current_chunk_tokens = 0

    current_content_item_index = 0 # Track position within content_indices

    while current_content_item_index < len(content_indices):
        original_list_index = content_indices[current_content_item_index]
        # Update chapter state based on the *full* list before processing content
        # Find the most recent chapter heading *before or at* this original index
        temp_chapter = current_chapter # Keep previous if none found before this item
        for j in range(original_list_index, -1, -1):
            _, _, ch_title_lookup, _ = sentences_structure[j]
            if ch_title_lookup is not None:
                temp_chapter = ch_title_lookup
                break
        if temp_chapter != current_chapter:
             # If chapter changed *before* this content item, finalize old chunk
             finalize_chunk()
             current_chapter = temp_chapter


        # Now process the actual content item
        text, page_num, _, _ = sentences_structure[original_list_index] # Ignore heading info here

        sentence_tokens = len(tokenizer.encode(text))

        # Check for chunk boundary
        if current_chunk_texts and (current_chunk_tokens + sentence_tokens > target_tokens) and sentence_tokens < target_tokens :
            finalize_chunk() # Finalize the previous chunk

            # --- Overlap Logic (Simplified) ---
            overlap_start_content_idx = max(0, current_content_item_index - overlap_sentences)
            for k in range(overlap_start_content_idx, current_content_item_index):
                 overlap_original_idx = content_indices[k]
                 o_text, o_page, _, _ = sentences_structure[overlap_original_idx]
                 o_tokens = len(tokenizer.encode(o_text))
                 current_chunk_texts.append(o_text)
                 current_chunk_pages.append(o_page)
                 current_chunk_tokens += o_tokens
            # --- End Overlap Logic ---

        # Add current text to the chunk
        current_chunk_texts.append(text)
        current_chunk_pages.append(page_num)
        current_chunk_tokens += sentence_tokens

        current_content_item_index += 1 # Move to the next content item

    finalize_chunk() # Add the last chunk

    return chunks_data
