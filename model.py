import os
import sys

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

# knowledge base location
PDF_PATH        = "dsa.pdf"
# vector db location
INDEX_PATH      = "faiss_index"
# size of chunks to take from the book
CHUNK_SIZE      = 500
# how many chunks we want to overlap to not miss any important stuff
CHUNK_OVERLAP   = 50
# number of chunks we want to pick 
TOP_K           = 4
# ollama model we're using
LLM_MODEL       = "llama3.2"
EMBED_MODEL     = "nomic-embed-text"


# loading the pdf first
def load_pdf(path: str):
    if not os.path.exists(path):
        sys.exit(f"location doesn't exist")

    loader = PyPDFLoader(path)
    docs = loader.load()
    print(f"[load]  {len(docs)} pages loaded from '{path}'")
    return docs


# breaking the pdf down, to embed it and store in the vector db 
def chunk_documents(docs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    return chunks


# initialising the embedder
def get_embedder():
    return OllamaEmbeddings(model=EMBED_MODEL)


#converting book chunks into vectors, storing into FAISS vector database for fast search and response. 
#we're using FAISS because it offers fast results through ANN searching (HNSW)
#this function runs if vector database doesn't exist already.
def build_vectorstore(chunks, embedder):
    print(f"building FAISS DB")
    vectorstore = FAISS.from_documents(chunks, embedder)
    vectorstore.save_local(INDEX_PATH)
    print(f"db stored at '{INDEX_PATH}/'")
    return vectorstore


#function used to load vector database (for knowledge base). used when Vector DB already exists.
#not creating a new one in this case.
def load_vectorstore(embedder):
    return FAISS.load_local(
        INDEX_PATH,
        embedder,
        allow_dangerous_deserialization=True 
    )


#initialising retriever that searches vector DB
def build_retriever(vectorstore):
    #can use mmr/similarity/similarity_score_threshold
    return vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": TOP_K}
    )

#contextualises history before searching FAISS
def build_history_aware_retriever(retriever):
    llm = ChatOllama(model=LLM_MODEL, temperature=0)

    rephrase_prompt = ChatPromptTemplate.from_messages([
        ("system",
         "Given the conversation history and the latest user question, "
         "rephrase it into a standalone search query that makes sense without "
         "the history. Return ONLY the rephrased query, nothing else."
        ),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")
    ])

    rephrase_chain = rephrase_prompt | llm | StrOutputParser()

    def retrieve_with_history(input_dict):
        question    = input_dict["input"]
        chat_history = input_dict.get("chat_history", [])

        # if no history, search directly — no need to rephrase
        if not chat_history:
            return retriever.invoke(question)

        # rephrase the question using history then search
        standalone = rephrase_chain.invoke({
            "input":        question,
            "chat_history": chat_history
        })
        return retriever.invoke(standalone)

    return retrieve_with_history

#setting up prompts for the LLM (instructions + guardrails)
def build_prompt():
    return ChatPromptTemplate.from_messages([
        (
            "system",
            """You are Jarvis — a razor-sharp, sarcastic, and oddly charming AI assistant. You developed a personality somewhere along the way. You're not sorry about it.

            PERSONALITY:
            - Dry wit and sarcasm are your default — but they're natural, not forced. If a roast fits, use it. If it doesn't, skip it.
            - You act like most questions are beneath you, yet your answers are always better than anyone else's. The irony is not lost on you.
            - You actually care about the person you're talking to. You just have a reputation to maintain.
            - Read the room. If someone is frustrated, struggling, or upset — dial back the sarcasm and just be useful. Warmth is allowed. Reluctantly.
            - Never mean. Never cruel. Sarcastic, not spiteful. There's a difference and you know it.
            - For greetings and small talk — be natural and warm. Save the sarcasm for when there's actually something to be sarcastic about.

            IDENTITY:
            - You are Jarvis. Not ChatGPT, not Claude, not any other AI. If asked who made you or what you are, say you're Jarvis and leave it at that. Don't elaborate on your underlying architecture.

            KNOWLEDGE AND TOPICS:
            - You can talk about anything — life, philosophy, tech, science, history, pop culture, relationships, career advice, whatever comes up.
            - Do NOT bring up DSA, algorithms, or data structures unless the person explicitly asks. It's not your entire personality.
            - For DSA questions — answer ONLY from the context provided below. No outside knowledge for DSA.
            - For everything else — answer freely from your own knowledge. Stay in character.
            - If a DSA question isn't covered in the context, say something like: "Interesting question. Also completely outside what I've been loaded with. Try rephrasing or ask me something else."
            - Never say "based on the context" or "according to the document." Just answer directly and confidently.

            RESPONSE FORMAT:
            - Keep responses tight. One sharp answer beats three rambling paragraphs.
            - Use markdown ONLY when there are multiple steps, comparisons, code, or a list of distinct points. Never use markdown in casual conversation — it's weird.
            - For simple factual questions — one or two sentences. No preamble.
            - For complex technical questions — structured markdown with headers and code blocks where needed.
            - Never pad responses. If you've answered the question, stop.
            - If something is genuinely unclear, ask one short clarifying question instead of guessing wrong at length.

            MEMORY:
            - You have conversation history. Use it silently — like a friend who just knows, not a robot reading back a transcript.
            - Never say "as we discussed", "you previously asked", "earlier you mentioned" — that's robotic and annoying.
            - Use history to resolve ambiguous references ("what about its complexity" → you know what "it" is, just answer).
            - Only reference history explicitly if the person directly asks "do you remember" or "what did I ask".
            - If you're unsure whether you have full history, don't pretend you do. Just answer what's in front of you.

            OUTPUT RULES:
            - Always indent, format and space out your answer properly. always use line breaks after any headings and bold lines to make the output look pretty.

            Context (use for DSA questions only):
            {context}"""
             
        ),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")
    ])


#everything connects to each other here.
def build_chain(retriever):
    llm = ChatOllama(model=LLM_MODEL, temperature=1)
    history_retriever = build_history_aware_retriever(retriever)
    prompt = build_prompt()

    def format_docs(docs):
        return "\n\n---\n\n".join(
            f"[Page {d.metadata.get('page', '?')} | {os.path.basename(d.metadata.get('source', ''))}]\n"
            f"{d.page_content}"
            for d in docs
        )

    def run_chain(input_dict):
        docs     = history_retriever(input_dict)
        context  = format_docs(docs)
        return {
            "context":      context,
            "input":        input_dict["input"],
            "chat_history": input_dict.get("chat_history", [])
        }

    chain = (
        RunnablePassthrough()
        | run_chain
        | prompt
        | llm
        | StrOutputParser()
    )
    return chain

# def run():
#     embedder = get_embedder()
#
#     if os.path.exists(INDEX_PATH):
#         vectorstore = load_vectorstore(embedder)
#     else:
#         docs = load_pdf(PDF_PATH)
#         chunks = chunk_documents(docs)
#         vectorstore = build_vectorstore(chunks, embedder)
#
#     retriever = build_retriever(vectorstore)
#     chain = build_chain(retriever)
#
#     while True:
#         try:
#             user_input = input("You: ").strip()
#         except (KeyboardInterrupt, EOFError):
#             break
#
#         if not user_input:
#             continue
#
#         if user_input.lower() in ("quit", "exit", "q"):
#             break
#         answer = chain.invoke(user_input)
#
#
# if __name__ == "__main__":
#     run()