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

    def finalize_chunk():
        nonlocal chunks_data, current_chunk_texts, current_chunk_pages, current_chunk_tokens, current_chapter, current_subchapter
        if current_chunk_texts:
            chunk_text_joined = " ".join(current_chunk_texts).strip() # Ensure stripped
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

    original_indices_map = {idx: (data[0], data[1], data[2], data[3]) for idx, data in enumerate(sentences_structure)}
    current_original_idx = 0

    while current_original_idx < len(sentences_structure):
        text, page_num, detected_ch_title, detected_sub_title = sentences_structure[current_original_idx]

        is_chapter_heading = detected_ch_title is not None
        is_subchapter_heading = detected_sub_title is not None

        if is_chapter_heading:
            finalize_chunk()
            current_chapter = detected_ch_title
            current_subchapter = None
            current_original_idx += 1 # Move past the chapter heading line
            continue

        if is_subchapter_heading:
            current_subchapter = detected_sub_title
            # Subchapter heading text is included in the chunk below

        sentence_tokens = len(tokenizer.encode(text))

        # Check for chunk boundary
        if current_chunk_texts and (current_chunk_tokens + sentence_tokens > target_tokens):
            finalize_chunk()

            # --- More Robust Overlap Logic ---
            overlap_start_index = -1
            sentences_to_overlap_count = 0
            # Search backwards in the *original* list from the point *before* the current index
            for j in range(current_original_idx - 1, -1, -1):
                # Check if the item at index j was actual content (not a chapter heading)
                if original_indices_map[j][2] is None: # It wasn't a chapter heading
                    sentences_to_overlap_count += 1
                    if sentences_to_overlap_count >= overlap_sentences:
                        overlap_start_index = j
                        break
            # If not enough content sentences found, just take the last few items regardless
            if overlap_start_index == -1:
                 overlap_start_index = max(0, current_original_idx - overlap_sentences)

            # Add overlap sentences to the new chunk
            for k in range(overlap_start_index, current_original_idx):
                 o_text, o_page, o_ch, o_sub = original_indices_map[k]
                 # Only add non-chapter headings to the new chunk's overlap
                 if o_ch is None:
                      o_tokens = len(tokenizer.encode(o_text))
                      # Avoid adding duplicates if the loop includes the current text
                      if k != current_original_idx:
                          current_chunk_texts.append(o_text)
                          current_chunk_pages.append(o_page)
                          current_chunk_tokens += o_tokens
            # --- End Overlap Logic ---


        # Add current text (sentence or subchapter heading) to the chunk
        current_chunk_texts.append(text)
        current_chunk_pages.append(page_num)
        current_chunk_tokens += sentence_tokens

        current_original_idx += 1 # Move to the next item in the original list

    finalize_chunk() # Add the last chunk

    return chunks_data
