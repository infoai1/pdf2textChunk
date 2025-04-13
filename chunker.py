# --- START OF FILE chunker.py ---
import tiktoken

def chunk_structured_sentences(sentences_structure, tokenizer, target_tokens, overlap_sentences):
    """
    Chunks sentences/headings, assigns last known chapter title.
    Assumes sentences_structure provides chapter/subchapter info when detected.
    Input: List of (text, page_num, chapter_title_if_heading, subchapter_title_if_heading) tuples.
    Output: List of dictionaries.
    """
    if not tokenizer: print("ERROR: Tokenizer not provided."); return []
    if not sentences_structure: print("Warning: No sentences provided."); return []

    chunks_data = []
    current_chunk_texts = []
    current_chunk_pages = []
    current_chunk_tokens = 0
    current_chapter = "Unknown Chapter / Front Matter" # Initial state
    current_subchapter = None # Initial state

    # Store original indices of *content* items (non-chapter headings)
    # Content includes regular sentences AND detected subchapter headings
    content_indices = [i for i, (_, _, ch, _) in enumerate(sentences_structure) if ch is None]

    def finalize_chunk():
        # Indentation Level 1
        nonlocal chunks_data, current_chunk_texts, current_chunk_pages, current_chunk_tokens, current_chapter, current_subchapter
        if current_chunk_texts:
            # Indentation Level 2
            chunk_text_joined = " ".join(current_chunk_texts).strip()
            start_page = current_chunk_pages[0] if current_chunk_pages else 0
            if chunk_text_joined:
                # Indentation Level 3
                chunks_data.append({
                    "chunk_text": chunk_text_joined,
                    "page_number": start_page,
                    "chapter_title": current_chapter,
                    "subchapter_title": current_subchapter # Assign current state
                })
            # Reset for next chunk (still Level 2)
            current_chunk_texts = []
            current_chunk_pages = []
            current_chunk_tokens = 0

    current_content_item_index = 0 # Track position within content_indices

    # --- Main Loop over Content Items --- (Indentation Level 0)
    while current_content_item_index < len(content_indices):
        # Indentation Level 1
        original_list_index = content_indices[current_content_item_index]

        # --- Update Chapter/Subchapter State before processing content item ---
        temp_chapter = current_chapter
        temp_subchapter = current_subchapter # Start with previous state for subchapter
        found_sub_after_last_chap = False
        for j in range(original_list_index, -1, -1):
            # Indentation Level 2
            _, _, ch_title_lookup, sub_title_lookup = sentences_structure[j]
            if ch_title_lookup is not None:
                # Indentation Level 3
                temp_chapter = ch_title_lookup
                if not found_sub_after_last_chap: temp_subchapter = None
                break # Stop searching back
            if sub_title_lookup is not None and not found_sub_after_last_chap:
                 # Indentation Level 3
                 temp_subchapter = sub_title_lookup
                 found_sub_after_last_chap = True

        # Check if state actually changed *before* this content item
        if temp_chapter != current_chapter:
            # Indentation Level 2
             finalize_chunk() # Finalize chunk under old chapter
             current_chapter = temp_chapter
             current_subchapter = temp_subchapter # This subchapter belongs to the new chapter
        elif temp_subchapter != current_subchapter:
            # Indentation Level 2
             # If only subchapter changed, update state but don't necessarily finalize chunk unless needed by size
             current_subchapter = temp_subchapter

        # --- Process the actual content item --- (Still Level 1)
        text, page_num, _, _ = sentences_structure[original_list_index] # Ignore heading info retrieved here

        sentence_tokens = len(tokenizer.encode(text))

        # Check for chunk boundary
        if current_chunk_texts and \
           ((current_chunk_tokens + sentence_tokens > target_tokens and sentence_tokens < target_tokens*0.8) or sentence_tokens >= target_tokens*1.5):
            # Indentation Level 2
            finalize_chunk() # Finalize the previous chunk

            # --- Overlap Logic ---
            overlap_start_content_idx = max(0, current_content_item_index - overlap_sentences)
            for k in range(overlap_start_content_idx, current_content_item_index):
                # Indentation Level 3
                overlap_original_idx = content_indices[k]
                if overlap_original_idx < len(sentences_structure):
                    # Indentation Level 4
                    o_text, o_page, _, _ = sentences_structure[overlap_original_idx]
                    o_tokens = len(tokenizer.encode(o_text)) # <--- THIS IS THE LINE FROM THE ERROR
                    current_chunk_texts.append(o_text)
                    current_chunk_pages.append(o_page)
                    current_chunk_tokens += o_tokens
                else:
                    # Indentation Level 4
                    print(f"Warning: Overlap index {overlap_original_idx} out of bounds.")
            # --- End Overlap Logic ---

        # Add current text to the chunk (Still Level 1)
        current_chunk_texts.append(text)
        current_chunk_pages.append(page_num)
        current_chunk_tokens += sentence_tokens

        current_content_item_index += 1 # Move to the next content item (Still Level 1)

    # Finalize the very last chunk (Indentation Level 0)
    finalize_chunk()

    return chunks_data
# --- END OF FILE chunker.py ---
