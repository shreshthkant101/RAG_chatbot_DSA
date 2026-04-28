import json
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from typing import List
from langchain_ollama import ChatOllama

# Importing constants and functions from our model. we will call these functions as we need them. 
from model import (
    PDF_PATH,
    INDEX_PATH,
    build_chain,
    build_retriever,
    chunk_documents,
    build_vectorstore,
    get_embedder,
    load_pdf,
    load_vectorstore,
)

# setting state (variable only)
state = {
    "embedder":    None,
    "vectorstore": None,
    "retriever":   None,
    "chain":       None,
    "ready":       False,
}


# -----------------------------------------------------------
# -------------- FASTAPI SERVER SETUP WORKFLOW --------------
# -----------------------------------------------------------




# initialising fastAPI here. This function runs the web server that we're hosting.
# we're also initialising our FAISS DB, embedder, retriever, and chain here.
@asynccontextmanager
async def lifespan(app: FastAPI):
    embedder = get_embedder()
    state["embedder"] = embedder

    if os.path.exists(INDEX_PATH):
        vectorstore = load_vectorstore(embedder)
    else:
        docs   = load_pdf(PDF_PATH)
        chunks = chunk_documents(docs)
        vectorstore = build_vectorstore(chunks, embedder)

    state["vectorstore"] = vectorstore
    state["retriever"]   = build_retriever(vectorstore)
    state["chain"]       = build_chain(state["retriever"])
    state["ready"]       = True

    # yeild here signifies the point where the server is ready to serve requests.
    yield

# setting up our fastAPI. lifespan: the function that FastAPI has to run when the server starts up and shuts down.
app = FastAPI(lifespan=lifespan)


# setting up CORS to allow requests from port 5173 (vite frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# setting up status endpoint (check server function)
@app.get("/status")
def health():
    return {"ready": state["ready"], "index": os.path.exists(INDEX_PATH)}




# --------------------------------------------------------------------
# -------------- VECTOR DB SETUP (LOAD/RELOAD) WORKFLOW --------------
# --------------------------------------------------------------------


# setting up ingest response framework (document ingestion status response only)
class IngestResponse(BaseModel):
    chunks: int
    status: str


# function to load knowledge base into vector DB 
@app.post("/ingest", response_model=IngestResponse)
def ingest():
    if not state["embedder"]:
        raise HTTPException(status_code=503, detail="Embedder not ready.")
    docs   = load_pdf(PDF_PATH)
    chunks = chunk_documents(docs)
    vs     = build_vectorstore(chunks, state["embedder"])
    state["vectorstore"] = vs
    state["retriever"]   = build_retriever(vs)
    state["chain"]       = build_chain(state["retriever"])
    return IngestResponse(chunks=len(chunks), status="ok")





# --------------------------------------------------------------
# -------------- ACTUAL INPUT - RESPONSE WORKFLOW --------------
# --------------------------------------------------------------



# defining format for SSE response.
def sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


# this is function that actually returns the responses in sse format
async def stream_response(question: str, history: list) -> AsyncGenerator[str, None]:

    #checking if model has been initialised or not.
    if not state["ready"]:
        yield sse({"type": "error", "content": "Model not ready yet."})
        return

    #if model is ready.
    try:
        # creating a new list for chat history (preparing for ollama.)
        chat_history = []
        
        # iterating through our history packet.
        for msg in history[-10:]:
            # assigning roles to history for ollama (HumanMessage/AIMessage)
            if msg["role"] == "user":
                chat_history.append(HumanMessage(content=msg["text"]))
            # only adding if ai returned a result
            elif msg["role"] == "ai" and msg["text"]:
                chat_history.append(AIMessage(content=msg["text"]))

        # final package to be factored into the prompt
        input_dict = {
            "input": question,
            "chat_history": chat_history
        }

        
        search_query = question


        # generating a rephrased search query only for FAISS in case of existing history. 
        if chat_history:
            rephrase_llm = ChatOllama(model="llama3.2", temperature=1)
            search_query = rephrase_llm.invoke(
                f"Rephrase this as a standalone search query given the conversation. "
                f"Return ONLY the query.\n\nQuestion: {question}\n\nHistory summary: "
                f"{' '.join([m.content for m in chat_history[-4:]])}"
            ).content

        # chunks we fetch from our DB
        docs = state["retriever"].invoke(search_query)

        # sources that the chunks were picked from
        sources = [
            {
                "page":  doc.metadata.get("page", "?"),
                "text":  doc.page_content,
                "score": round(1 - (i * 0.08), 2),
            }
            for i, doc in enumerate(docs)
        ]

        # returning sources before answer.
        yield sse({"type": "sources", "chunks": sources})


        # actual response being generated here. 
        #notice how we're using the original question in our input_dict, instead of the new search_query variable.
        #this is because the search_query variable was created only for vector search.
        # we already have our context chunks, the current question, and the search history.
        # since ollama is already getting all that, it doesnt need us to rephrase the current question.
        async for chunk in state["chain"].astream(input_dict):
            if chunk:
                yield sse({"type": "token", "content": chunk})

        yield sse({"type": "done"})

    except Exception as e:
        yield sse({"type": "error", "content": str(e)})


#initialising structure of recieved POST packet to be parsed
class QueryRequest(BaseModel):
    question: str
    history:  List[dict] = []

@app.post("/query")
async def query(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    return StreamingResponse(
        stream_response(req.question, req.history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )