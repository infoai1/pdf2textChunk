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
    current_chapter = "Unknown Chapter / Front Matter" # Initial state
    current_subchapter = None

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

    for i, (text, page_num, detected_ch_title, detected_sub_title) in enumerate(sentences_structure):

        if detected_ch_title is not None:
            finalize_chunk()
            current_chapter = detected_ch_title
            current_subchapter = None
            continue # Skip heading text

        if detected_sub_title is not None:
            current_subchapter = detected_sub_title
            # Subchapter heading text *is* currently included in the chunk

        sentence_tokens = len(tokenizer.encode(text))

        if current_chunk_texts and (current_chunk_tokens + sentence_tokens > target_tokens):
            finalize_chunk()

            # Overlap Logic (simplified: use last N texts/pages from finalized chunk)
            overlap_start_idx = max(0, len(chunks_data[-1]['chunk_text'].split()) - (overlap_sentences * 15)) # Estimate word count for overlap
            # This overlap logic needs improvement if exact sentence overlap is critical after chunking.
            # A better way would be to store the tuples in the chunk temporarily.
            # For now, sticking to simpler text-based overlap estimate:
            last_chunk_words = chunks_data[-1]['chunk_text'].split()
            overlap_text = " ".join(last_chunk_words[-overlap_start_idx:]) if overlap_start_idx > 0 else ""
            
            if overlap_text:
                 overlap_tokens = len(tokenizer.encode(overlap_text))
                 # Start new chunk with overlap text (page number might be slightly off here)
                 current_chunk_texts.append(overlap_text)
                 current_chunk_pages.append(chunks_data[-1]['page_number']) # Approximate page
                 current_chunk_tokens += overlap_tokens


            # Add the current sentence/subheading (that caused overflow)
            current_chunk_texts.append(text)
            current_chunk_pages.append(page_num)
            current_chunk_tokens += sentence_tokens

        else:
            current_chunk_texts.append(text)
            current_chunk_pages.append(page_num)
            current_chunk_tokens += sentence_tokens

    finalize_chunk() # Add the last chunk

    return chunks_data
