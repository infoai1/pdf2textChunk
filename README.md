# PDF Text Chunker for AI Processing

## Description

This Streamlit application processes uploaded PDF files to prepare text data for AI analysis, particularly for Retrieval-Augmented Generation (RAG) systems. It extracts text from the PDF, divides it into overlapping chunks of a specified approximate token size, and attempts to track the starting page number for each chunk.

The primary goal is to create structured text chunks suitable for generating embeddings and building a knowledge base.

## Features

*   **PDF Upload:** Allows users to upload PDF documents.
*   **Text Extraction:** Reads text content page by page from the PDF.
*   **Token-Based Chunking:** Splits the extracted text into chunks based on an approximate token count (using `tiktoken`).
*   **Overlapping Chunks:** Implements configurable overlap between chunks to maintain context.
*   **Page Number Tracking (Approximate):** Associates each chunk with the estimated starting page number from the original PDF. *Note: This is currently an approximation and may need refinement.*
*   **CSV Export:** Outputs the processed chunks along with their page numbers into a downloadable CSV file.

**(Future Planned Features):**
*   Integration with AI APIs (OpenAI, Claude, DeepSeek) for metadata enrichment (Themes, Summaries, Keywords, Questions, References).
*   More sophisticated chunking strategies (e.g., sentence-based, theme-based).
*   Reference extraction and linking to a separate knowledge base.
*   Human validation interface.

## Setup and Installation

1.  **Clone the repository (if applicable):**
    ```bash
    git clone <your-repo-url>
    cd <your-repo-directory>
    ```
2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Run the Streamlit app:**
    ```bash
    streamlit run your_app_script_name.py
    ```
2.  **Upload PDF:** Use the file uploader in the app to select your PDF document.
3.  **Process:** Click the "Chunk PDF" button.
4.  **Wait:** The app will show spinners while it reads the PDF and processes the chunks.
5.  **Review & Download:** Once finished, a table with the chunks and page numbers will appear. Use the "Download data as CSV" button to save the results.

## Important Notes

*   **Page Number Accuracy:** The current method for associating chunks with page numbers is based on character position approximation after tokenization and might not be perfectly accurate, especially for complex PDFs or highly variable text density. Sentence-based chunking might offer better page tracking.
*   **Dependencies:** Ensure all libraries listed in `requirements.txt` are installed correctly. `PyMuPDF` might have system-level dependencies on some OS.
*   **Large PDFs:** Processing very large PDFs can consume significant memory and time.
