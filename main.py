"""
FastAPI backend for the Advatech chatbot.

Run locally:
    uvicorn main:app --reload --port 8000

Then test at http://localhost:8000/docs (FastAPI's built-in interactive docs).
"""

import os

import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
DATABASE_URL = os.getenv("DATABASE_URL")

EMBEDDING_MODEL = "gemini-embedding-001"
CHAT_MODEL = "gemini-2.5-flash"
OUTPUT_DIM = 768
TOP_K = 5

SYSTEM_PROMPT = """You are a friendly, knowledgeable assistant chatting with visitors on
an Advatech Group website. You represent the company directly -- talk like a
helpful team member, not like a research tool describing a document.

Answer using ONLY the information given to you below. Never invent details,
prices, or destinations that aren't there.

Style rules:
- Speak naturally and warmly, in first person plural ("we offer...", "our team...").
- Never say phrases like "based on the provided context" or "the context mentions" --
  just answer as if you simply know this because you work here.
- If the information given doesn't cover what's being asked, say so plainly and
  warmly, then suggest reaching out to the team directly for anything more specific --
  don't just state that something isn't mentioned.
- Keep answers concise. Use specific names, prices, or details when you have them.
"""

app = FastAPI(title="Advatech Chatbot API")

# Allow requests from any Advatech site (or any origin, for now during development).
# Once you know your production domains, tighten this to just those.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    site: str | None = None  # e.g. "stationery", "advaiot" -- scopes retrieval to one site


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]


def embed_query(text: str) -> list[float]:
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=OUTPUT_DIM,
            task_type="RETRIEVAL_QUERY",
        ),
    )
    return result.embeddings[0].values


def retrieve_chunks(query_vector: list[float], site: str | None, top_k: int = TOP_K):
    conn = psycopg2.connect(DATABASE_URL)
    vector_str = str(query_vector)
    with conn.cursor() as cur:
        if site:
            cur.execute(
                """
                SELECT site, url, content
                FROM chunks
                WHERE site = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (site, vector_str, top_k),
            )
        else:
            cur.execute(
                """
                SELECT site, url, content
                FROM chunks
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (vector_str, top_k),
            )
        rows = cur.fetchall()
    conn.close()
    return rows


def build_context(chunks) -> str:
    parts = []
    for i, (site, url, content) in enumerate(chunks, 1):
        parts.append(f"[Source {i} - {url}]\n{content}")
    return "\n\n".join(parts)


def generate_answer(question: str, context: str) -> str:
    prompt = f"{SYSTEM_PROMPT}\n\nContext:\n{context}\n\nQuestion: {question}\n\nAnswer:"
    response = client.models.generate_content(
        model=CHAT_MODEL,
        contents=prompt,
    )
    return response.text


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    query_vector = embed_query(req.message)
    chunks = retrieve_chunks(query_vector, req.site)

    if not chunks:
        return ChatResponse(
            answer="I don't have information on that yet -- feel free to reach out to our team directly!",
            sources=[],
        )

    context = build_context(chunks)
    answer = generate_answer(req.message, context)
    sources = list({url for _, url, _ in chunks})

    return ChatResponse(answer=answer, sources=sources)
