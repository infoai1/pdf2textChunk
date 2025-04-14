# --- START OF FILE chunker.py ---
import tiktoken

def chunk_structured_sentences(sentences_structure, tokenizer, target_tokens, overlap_sentences):
    """
    Chunks sentences/headings, assigns last known chapter title.
    Assumes sentences_structure provides chapter/subchapter info when detected.
    Input: List of (text, page_num_marker, chapter_title_if_heading, subchapter_title_if_heading) tuples.
    Output: List of dictionaries.
    """
    if not tokenizer: print("ERROR: Tokenizer not provided."); return []
    if not sentences_structure: print("Warning: No sentences provided."); return []

    chunks_data = []
    current_chunk_texts = []
    current_chunk_pages = [] # Stores page numbers or para markers
    current_chunk_tokens = 0
    current_chapter = "Unknown Chapter / Front Matter" # Initial state
    current_subchapter = None # Initial state

    # Store original indices of *content* items (non-chapter headings)
    content_indices = [i for i, (_, _, ch, _) in enumerate(sentences_structure) if ch is None]

    def finalize_chunk():
        nonlocal chunks_data, current_chunk_texts, current_chunk_pages, current_chunk_tokens, current_chapter, current_subchapter
        if current_chunk_texts:
            chunk_text_joined = " ".join(current_chunk_texts).strip()
            start_marker = current_chunk_pages[0] if current_chunk_pages else "N/A"
            if chunk_text_joined:
                chunks_data.append({
                    "chunk_text": chunk_text_joined,
                    "page_number": start_marker, # Use the marker
                    "chapter_title": current_chapter,
                    "subchapter_title": current_subchapter # Assign current state
                })
            current_chunk_texts, current_chunk_pages, current_chunk_tokens = [], [], 0

    current_content_item_index = 0

    while current_content_item_index < len(content_indices):
        original_list_index = content_indices[current_content_item_index]

        # Find most recent chapter/subchapter state *before* this item
        temp_chapter = current_chapter
        temp_subchapter = current_subchapter
        found_sub_after_last_chap = False
        for j in range(original_list_index, -1, -1):
            _, _, ch_title_lookup, sub_title_lookup = sentences_structure[j]
            if ch_title_lookup is not None:
                temp_chapter = ch_title_lookup
                if not found_sub_after_last_chap: temp_subchapter = None # Reset sub when chapter changes
                break
            if sub_title_lookup is not None and not found_sub_after_last_chap:
                 temp_subchapter = sub_title_lookup
                 found_sub_after_last_chap = True

        # Update state if changed
        if temp_chapter != current_chapter:
            finalize_chunk() # Finalize chunk under old chapter/subchapter
            current_chapter = temp_chapter
            current_subchapter = temp_subchapter
        elif temp_subchapter != current_subchapter:
             # If only subchapter changed, finalize previous chunk before starting new context
             # This helps group content under the correct subchapter more cleanly
             finalize_chunk()
             current_subchapter = temp_subchapter

        # Process the content item
        text, page_marker, _, _ = sentences_structure[original_list_index]
        try: sentence_tokens = len(tokenizer.encode(text))
        except Exception as e: print(f"Tokenize Error: {e}"); current_content_item_index += 1; continue

        # Check chunk boundary condition
        # Finalize if chunk has text AND (adding sentence exceeds target OR sentence itself is huge)
        if current_chunk_texts and \
           ((current_chunk_tokens + sentence_tokens > target_tokens and sentence_tokens < target_tokens) or sentence_tokens >= target_tokens):
             finalize_chunk()

             # --- Overlap Logic ---
             overlap_start_content_idx = max(0, current_content_item_index - overlap_sentences)
             for k in range(overlap_start_content_idx, current_content_item_index):
                 overlap_original_idx = content_indices[k]
                 if overlap_original_idx < len(sentences_structure):
                     o_text, o_marker, _, _ = sentences_structure[overlap_original_idx]
                     try:
                         o_tokens = len(tokenizer.encode(o_text))
                         current_chunk_texts.append(o_text)
                         current_chunk_pages.append(o_marker)
                         current_chunk_tokens += o_tokens
                     except Exception as e: print(f"Error encoding overlap: {e}")
                 else: print(f"Warn: Overlap index {overlap_original_idx} OOB.")
             # --- End Overlap Logic ---


        # Add current text to the chunk
        current_chunk_texts.append(text)
        current_chunk_pages.append(page_marker)
        current_chunk_tokens += sentence_tokens

        current_content_item_index += 1

    finalize_chunk() # Add last chunk
    return chunks_data
# --- END OF FILE chunker.py ---
