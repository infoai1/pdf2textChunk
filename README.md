# PDF Structured Text Chunker for AI Processing

## Description

This Streamlit application processes uploaded PDF files to prepare text data for AI analysis, particularly for Retrieval-Augmented Generation (RAG) systems. It aims to:

*   Extract text content from the PDF.
*   Allow skipping of initial and final pages (e.g., covers, indexes).
*   Allow setting the correct starting page number for accurate tracking.
*   Clean common metadata/footer elements.
*   **Detect Chapter and Subchapter headings using heuristics based on text formatting and estimated font sizes.** (Requires tuning per document style).
*   Divide the cleaned text into overlapping, sentence-based chunks targeting a specific token count.
*   Ensure chunks do not span across detected **Chapter** boundaries.
*   Associate each chunk with its corresponding page number, detected Chapter title, and detected Subchapter title.
*   Export the results as a CSV file.

## Features

*   PDF Upload.
*   Configurable Page Skipping (Start/End).
*   Configurable Starting Page Number Offset.
*   Basic Metadata/Footer Cleaning.
*   Heuristic-Based Chapter/Subchapter Detection (using font size estimates and text patterns).
*   Sentence Tokenization via NLTK.
*   Token-Aware Chunking (via `tiktoken`) with Sentence-Based Overlap.
*   Chapter Boundary Respect during Chunking.
*   CSV Export with columns: `chunk_text`, `page_number`, `chapter_title`, `subchapter_title`.

## Setup and Installation

1.  **Clone the repository (if applicable).**
2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Run NLTK Download (First Time):** The app will attempt to download necessary NLTK data ('punkt', 'punkt_tab') on first run if needed. Ensure you have an internet connection.

## Usage

1.  **Run the Streamlit app:**
    ```bash
    streamlit run app.py
    ```
2.  **Configure Options (Sidebar):**
    *   Set the number of pages to skip at the start and end.
    *   Set the actual page number printed on the first page *after* skipping the initial ones.
3.  **Upload PDF:** Use the file uploader.
4.  **Process:** Click the "Process PDF" button.
5.  **Wait:** Monitor progress in the app.
6.  **Review & Download:** Inspect the resulting DataFrame and download the CSV.

## Important Notes & Tuning

*   **HEADING DETECTION IS HEURISTIC:** The accuracy of chapter/subchapter detection **highly depends** on the consistency of formatting within your PDF and the rules defined in `pdf_utils.py` (specifically `is_likely_chapter_heading_fs` and `is_likely_subchapter_heading_fs`). **You will likely need to adjust the thresholds and patterns in these functions for optimal results with different books.** Use print statements locally for debugging font sizes and decisions.
*   **Font Analysis:** Relies on `PyMuPDF`'s ability to extract font size info. May not work perfectly on all PDFs (e.g., scanned images).
*   **Dependencies:** Ensure all libraries in `requirements.txt` are installed. `PyMuPDF` might have system dependencies.
*   **Large PDFs:** Processing can be memory and time-intensive.
