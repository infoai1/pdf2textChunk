import tiktoken

def chunk_structured_sentences(sentences_structure, tokenizer, target_tokens, overlap_sentences):
    """Chunks sentences, respecting chapters and associating titles."""
    if not tokenizer: print("ERROR: Tokenizer not provided."); return []
    if not sentences_structure: print("Warning: No sentences provided."); return []

    chunks_data = []
    current_chunk_texts = []
    current_chunk_pages = []
    current_chunk_tokens = 0
    current_chapter = "Unknown Chapter / Front Matter"
    current_subchapter = None

    # Store original indices of *content* items only (not chapter headings)
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
        text, page_num, _, detected_sub_title = sentences_structure[original_list_index] # Ignore chapter title here

        # Update subchapter if this line detected one
        if detected_sub_title is not None:
            current_subchapter = detected_sub_title
            # Treat the subheading text as content for the chunk

        sentence_tokens = len(tokenizer.encode(text))

        # Check for chunk boundary
        if current_chunk_texts and (current_chunk_tokens + sentence_tokens > target_tokens):
            finalize_chunk()

            # --- Overlap Logic ---
            # Find the index in the *content_indices* list for the start of the overlap
            overlap_start_content_index = max(0, current_content_item_index - overlap_sentences)
            
            # Add overlap sentences to the new chunk
            for k in range(overlap_start_content_index, current_content_item_index):
                 overlap_original_idx = content_indices[k]
                 o_text, o_page, _, o_sub = sentences_structure[overlap_original_idx]
                 # Note: If the overlap includes a subchapter heading, its state effect (`current_subchapter`)
                 # might be reapplied here based on the next iteration. This could be refined.
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

    return chunks_data
