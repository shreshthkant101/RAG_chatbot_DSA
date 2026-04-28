# Jarvis — RAG-Powered DSA Chatbot

**Version 1.0**

Jarvis is a locally-hosted, AI-powered chatbot built around Retrieval-Augmented Generation (RAG). It uses a PDF knowledge base (a DSA textbook) to answer questions accurately, while maintaining a conversational personality that goes well beyond a typical Q&A bot. Everything runs on your machine — no external APIs, no data leaving your system.

------

## What It Does

- Answers DSA questions grounded in a real textbook, not hallucinated knowledge
- Streams responses token-by-token in real time (no waiting for a full answer to generate)
- Shows which pages of the book each answer was sourced from
- Maintains conversation history so follow-up questions work naturally
- Handles general conversation outside of DSA too — Jarvis has a personality. 

------

## Tech Stack

| Layer                     | Technology                          |
| ------------------------- | ----------------------------------- |
| LLM                       | Ollama · `llama3.2` (Via Langchain) |
| Embeddings                | Ollama · `nomic-embed-text`         |
| Vector Database           | FAISS (via LangChain)               |
| Backend (Hosting Wrapper) | FastAPI                             |
| Streaming                 | Server-Sent Events (SSE) (Realtime) |
| Frontend                  | React (Vite)                        |
| Markdown Rendering        | `react-markdown`                    |

------

## Architecture & How It Works

### Full Pipeline

```
User Question
     │
     ▼
[ React Frontend ]
  - Sends question + last 10 messages of history to FastAPI via POST /query
     │
     ▼
[ FastAPI Backend ]
  - Receives the request
  - If chat history exists → rephrases the question into a standalone search query
    using llama3.2 (so FAISS gets a clean, context-aware query)
     │
     ▼
[ FAISS Vector Store ]
  - Searches for the top 4 most relevant chunks from the embedded DSA PDF
  - Returns chunks with page metadata
     │
     ▼
[ LangChain Chain ]
  - Formats retrieved chunks as context
  - Builds full prompt: system instructions + chat history + context + question
  - Sends to llama3.2 via Ollama
     │
     ▼
[ Streaming Response ]
  - Sources (page numbers + relevance scores) are sent first
  - Answer is streamed token-by-token via SSE
  - Frontend renders tokens in real time using ReactMarkdown
```

### How the Vector Store Gets Built

On first startup, if no FAISS index exists:

- The PDF is loaded page by page using `PyPDFLoader`
- Split into 500-character chunks with 50-character overlap using `RecursiveCharacterTextSplitter`
- Each chunk is embedded using `nomic-embed-text` via Ollama
- Stored in a local FAISS index saved to disk as `faiss_index/`

On subsequent startups, the saved index is loaded directly — no re-embedding needed.

You can also force a re-index anytime by hitting `POST /ingest`.

### History-Aware Retrieval

When a user asks a follow-up like *"what about its time complexity?"*, the word "its" is ambiguous to a search engine. Before querying FAISS, the backend uses `llama3.2` to rephrase the question into a standalone query (e.g., *"time complexity of merge sort"*) using the last 4 messages of conversation history. The original question is still sent to the LLM for answer generation — rephrasing is only used for the vector search step.

------

## Project Structure

```
jarvis/
│
├── backend/
│   ├── main.py          # FastAPI server, routes, SSE streaming logic
│   ├── model.py         # PDF loading, chunking, embedding, FAISS, chain setup. This is Our Model.
│   └── dsa.pdf          # Knowledge base (place your PDF here)
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Root component, state management, fetch logic
│   │   ├── main.jsx             # React entry point
│   │   ├── index.css            # Global styles
│   │   └── components/
│   │       ├── ChatPanel.jsx    # Message list, markdown rendering, scroll control
│   │       ├── InputBar.jsx     # Textarea, send button, keyboard handling
│   │       ├── CopyButton.jsx   # Copy-to-clipboard per message
│   │       └── navigationBar.jsx  # (Planned) Multi-chat navigation
│   └── ...
```

------

## Prerequisites

Make sure the following are installed before running the project.

**Ollama** — download from [ollama.com](https://ollama.com/)

After installing Ollama, pull the required models:

```bash
ollama pull llama3.2
ollama pull nomic-embed-text
```

**Python 3.10+**

**Node.js 18+**

------

## Setup & Running

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd jarvis
```

### 2. Backend setup

```bash
cd backend
pip install fastapi uvicorn langchain langchain-community langchain-ollama faiss-cpu pypdf
```

Place your `dsa.pdf` file in the `backend/` directory.

Start the backend server:

```bash
uvicorn main:app --reload --port 8000
```

On first run, the server will build the FAISS vector index from the PDF. This may take a minute or two depending on PDF size. Subsequent startups load the saved index instantly.

Verify the backend is ready:

```
GET http://localhost:8000/status
→ { "ready": true, "index": true } 
```

### 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The app will be running at `http://localhost:5173`.

### 4. (Optional) Force re-index the knowledge base

If you update the PDF and want to rebuild the vector store:

```
POST http://localhost:8000/ingest
```

------

## API Reference

| Method | Endpoint  | Description                                                |
| ------ | --------- | ---------------------------------------------------------- |
| `GET`  | `/status` | Returns whether the model and index are ready              |
| `POST` | `/ingest` | Re-builds the FAISS vector store from the PDF              |
| `POST` | `/query`  | Accepts a question + history, streams back an SSE response |

### `/query` request body

```json
{
  "question": "What is the time complexity of quicksort?",
  "history": [
    { "role": "user", "text": "Explain merge sort." },
    { "role": "ai", "text": "Merge sort is a divide-and-conquer..." }
  ]
}
```

### `/query` SSE event types

| Event type | Payload              | Description                                           |
| ---------- | -------------------- | ----------------------------------------------------- |
| `sources`  | `{ chunks: [...] }`  | Page numbers and relevance scores of retrieved chunks |
| `token`    | `{ content: "..." }` | One streamed token of the answer                      |
| `done`     | —                    | Signals the response is complete                      |
| `error`    | `{ content: "..." }` | Something went wrong                                  |

------

## Configuration

All tunable parameters are in `model.py`:

```python
CHUNK_SIZE    = 500    # Characters per document chunk
CHUNK_OVERLAP = 50     # Overlap between chunks
TOP_K         = 4      # Number of chunks retrieved per query
LLM_MODEL     = "llama3.2"
EMBED_MODEL   = "nomic-embed-text"
```

------

## Jarvis — Personality Notes

The system prompt defines Jarvis as a dry, sarcastic, but genuinely helpful AI. A few design decisions baked in:

- Sarcasm is natural, not forced — it dials back when the user is struggling or frustrated
- Does not bring up DSA unprompted — it's not his whole identity
- For DSA questions, answers only from retrieved context (no hallucination)
- For everything else, answers freely from general knowledge
- Never references "the document" or "based on context" — just answers directly
- Conversation history is used silently — no "as we discussed earlier" robotics
- Responses use markdown only when the structure actually earns it

------

## Upcoming Features — v1.0 -> v1.3 Roadmap

- **Favicon** — Generate and integrate favicon for window. (v1.1)
- **UI responsiveness** — full mobile and tablet support across all screen sizes (v1.1)
- **Emoji integration** — natural emoji usage in responses based on conversational tone(v1.1)
- **Visuals integration** — inline diagrams and illustrations for DSA concepts (trees, graphs, sorting steps, etc.) (v1.1)
- **Multiple chat windows** — open and manage separate conversations simultaneously (v1.2)
- **Navigation bar** (React Router) — sidebar to browse, switch between, and name saved chats (v1.2)
- **Persistent chat memory** — all conversations saved to server-side storage, resumable across sessions (v1.2)
- **User Authentication** — Multiple users can log in and chat simultaneously. Chat history for every account gets retained. (v1.3)
- **Additional Knowledge Base Sources ** — Add more books and documents to get more accurate and diverse results.

------

## Current Limitations (v1.0)

- Chat history is held in React state only — refreshing the page clears it
- Only one PDF knowledge base supported at a time
- No user authentication — intended for local single-user use
- FAISS does not support incremental updates — re-ingest required for any PDF changes. 

------

*Built by Shreshth Kant*