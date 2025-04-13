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
  # --- Simplified Main Loop for Debugging --- (Replace the original while loop)
while current_content_item_index < len(content_indices):
    # Indentation Level 1
    original_list_index = content_indices[current_content_item_index]
    text, page_num, _, _ = sentences_structure[original_list_index] # Get text

    # --- Minimal processing ---
    try: # Add try-except around the suspected line
        tokens_dummy = len(tokenizer.encode(text)) # Test encoding the text
        print(f"Processing item {current_content_item_index}, Text: '{text[:50]}...'") # Print progress
    except Exception as e:
        print(f"Error encoding text at index {current_content_item_index}: {e}")

    # --- VERY simple chunking - just add the item (ignore size/overlap for now) ---
    current_chunk_texts.append(text)
    current_chunk_pages.append(page_num)
    # Finalize chunk immediately for testing? Or after loop? Let's finalize after loop.

    current_content_item_index += 1 # Move to the next content item (Still Level 1)

# Finalize the very last chunk (Indentation Level 0)
finalize_chunk()
# --- End Simplified Loop ---

return chunks_data # Make sure this return is outside the loop
