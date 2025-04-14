# --- START OF FILE chunker.py ---
import tiktoken

def chunk_structured_sentences(sentences_structure, tokenizer, target_tokens, overlap_sentences):
    """
    Chunks sentences/headings based on tokens, assigns last known chapter title.
    Input: List of (text, page_num_marker, detected_chapter_title) tuples.
    Output: List of dictionaries [{'chunk_text': ..., 'page_number': ..., 'title': ...}]
    """
    if not tokenizer: print("ERROR: Tokenizer not provided."); return []
    if not sentences_structure: print("Warning: No sentences provided."); return []

    chunks_data = []
    current_chunk_texts = []
    current_chunk_pages = [] # Still track page/para markers
    current_chunk_tokens = 0
    current_chapter = "Unknown Chapter / Front Matter"

    # Indices of content items (non-chapter headings)
    content_indices = [i for i, (_, _, ch) in enumerate(sentences_structure) if ch is None]

    def finalize_chunk():
        nonlocal chunks_data, current_chunk_texts, current_chunk_pages, current_chunk_tokens, current_chapter
        if current_chunk_texts:
            chunk_text_joined = " ".join(current_chunk_texts).strip()
            start_marker = current_chunk_pages[0] if current_chunk_pages else "N/A"
            if chunk_text_joined:
                chunks_data.append({
                    "chunk_text": chunk_text_joined,
                    "page_number": start_marker,
                    "title": current_chapter # Use 'title' as the key
                })
            current_chunk_texts, current_chunk_pages, current_chunk_tokens = [], [], 0

    current_content_item_index = 0

    while current_content_item_index < len(content_indices):
        original_list_index = content_indices[current_content_item_index]

        # Find most recent chapter heading before this item
        temp_chapter = current_chapter
        for j in range(original_list_index, -1, -1):
            _, _, ch_title_lookup = sentences_structure[j]
            if ch_title_lookup is not None: temp_chapter = ch_title_lookup; break

        if temp_chapter != current_chapter:
            finalize_chunk(); current_chapter = temp_chapter

        text, page_marker, _ = sentences_structure[original_list_index]
        try: sentence_tokens = len(tokenizer.encode(text))
        except Exception as e: print(f"Tokenize Error: {e}"); current_content_item_index += 1; continue

        # Check chunk boundary
        if current_chunk_texts and \
           ((current_chunk_tokens + sentence_tokens > target_tokens and sentence_tokens < target_tokens) or sentence_tokens >= target_tokens):
            finalize_chunk()
            # Overlap Logic
            overlap_start_content_idx = max(0, current_content_item_index - overlap_sentences)
            for k in range(overlap_start_content_idx, current_content_item_index):
                overlap_original_idx = content_indices[k]
                if overlap_original_idx < len(sentences_structure):
                    o_text, o_marker, _ = sentences_structure[overlap_original_idx]
                    try:
                        o_tokens = len(tokenizer.encode(o_text))
                        current_chunk_texts.append(o_text)
                        current_chunk_pages.append(o_marker)
                        current_chunk_tokens += o_tokens
                    except Exception as e: print(f"Error encoding overlap: {e}")
                else: print(f"Warn: Overlap index {overlap_original_idx} OOB.")

        # Add current text if not identical to last overlap text
        if not current_chunk_texts or text != current_chunk_texts[-1]:
            current_chunk_texts.append(text)
            current_chunk_pages.append(page_marker)
            current_chunk_tokens += sentence_tokens
        elif not current_chunk_pages or page_marker != current_chunk_pages[-1]:
             current_chunk_pages.append(page_marker)

        current_content_item_index += 1

    finalize_chunk()
    return chunks_data


def chunk_by_chapter(sentences_structure):
    """
    Groups all text under the most recently detected chapter title.
    Input: List of (text, page_num_marker, detected_chapter_title) tuples.
    Output: List of dictionaries [{'title': chapter_title, 'chunk_text': all_text_for_chapter}]
    """
    if not sentences_structure: return []

    chunks_by_chapter = {}
    current_chapter = "Unknown Chapter / Front Matter" # Default for text before first heading

    for text, _, detected_title in sentences_structure:
        if detected_title is not None:
            current_chapter = detected_title # Update chapter when heading is found
            if current_chapter not in chunks_by_chapter:
                 chunks_by_chapter[current_chapter] = [] # Initialize list for new chapter
            # Don't add the heading text itself to the chunk text
        else:
            # Add regular text to the *current* chapter's list
            if current_chapter not in chunks_by_chapter:
                 chunks_by_chapter[current_chapter] = [] # Initialize if needed
            chunks_by_chapter[current_chapter].append(text)

    # Format the output
    output_list = []
    for title, texts in chunks_by_chapter.items():
        if texts: # Only output chapters that have text content
            output_list.append({
                "title": title,
                "chunk_text": " ".join(texts).strip() # Join all text for the chapter
            })

    return output_list

# --- END OF FILE chunker.py ---
