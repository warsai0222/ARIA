"""
ARIA Knowledge Base Ingestion Script

Reads data/varshith.json, chunks it into semantic units,
embeds each chunk with Google text-embedding-004,
and upserts to Qdrant Cloud.

Usage:
    python scripts/ingest.py

Env vars required:
    GOOGLE_API_KEY
    QDRANT_URL
    QDRANT_API_KEY
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv()

from google import genai
from google.genai import types as genai_types
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

COLLECTION = "aria_chunks"
VECTOR_DIM = 768
EMBEDDING_MODEL = "text-embedding-004"
DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "varshith.json"


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def build_chunks(data: dict) -> list[dict]:
    """Convert varshith.json into a flat list of semantic chunks."""
    chunks: list[dict] = []

    # About
    about = data.get("about", {})
    chunks.append({
        "section": "about",
        "name": "About Varshith Tipirneni",
        "text": (
            f"Name: {about.get('name', 'Varshith Tipirneni')}\n"
            f"Title: {about.get('title', '')}\n"
            f"Tagline: {about.get('tagline', '')}\n"
            f"Status: {about.get('status', '')}\n"
            f"Summary: {about.get('summary', '')}\n"
            f"Philosophy: {about.get('philosophy', '')}\n"
            f"Timezone: {about.get('timezone', '')}"
        ),
    })

    # Education
    for edu in data.get("education", []):
        highlights = "\n".join(f"- {h}" for h in edu.get("highlights", []))
        chunks.append({
            "section": "education",
            "name": f"Education — {edu.get('institution', '')}",
            "text": (
                f"Education: {edu.get('degree', '')} at {edu.get('institution', '')}\n"
                f"Duration: {edu.get('dates', '')}\n"
                f"Highlights:\n{highlights}"
            ),
        })

    # Experience
    for exp in data.get("experience", []):
        bullets = "\n".join(f"- {b}" for b in exp.get("impact_bullets", []))
        chunks.append({
            "section": "experience",
            "name": f"{exp.get('role', '')} at {exp.get('company', '')}",
            "text": (
                f"Role: {exp.get('role', '')} at {exp.get('company', '')}\n"
                f"Duration: {exp.get('dates', '')}\n"
                f"Type: {exp.get('type', '')}\n"
                f"Key achievements:\n{bullets}"
            ),
        })

    # Projects — one detailed chunk per project
    for proj in data.get("projects", []):
        features = "\n".join(f"- {f}" for f in proj.get("key_features", []))
        bullets = "\n".join(f"- {b}" for b in proj.get("resume_bullets", []))
        links = proj.get("links", {})
        links_str = "\n".join(f"  {k}: {v}" for k, v in links.items())
        chunks.append({
            "section": "project",
            "name": f"Project: {proj.get('name', '')}",
            "text": (
                f"Project: {proj.get('name', '')} [{proj.get('status', '')}]\n"
                f"Description: {proj.get('description', '')}\n"
                f"Problem solved: {proj.get('problem', '')}\n"
                f"Architecture: {proj.get('architecture', '')}\n"
                f"Tech stack: {', '.join(proj.get('tech_stack', []))}\n"
                f"Key features:\n{features}\n"
                f"Results: {proj.get('results', '')}\n"
                f"Resume bullets:\n{bullets}\n"
                f"Links:\n{links_str}"
            ),
        })

    # Skills — one chunk per category
    for category, items in data.get("skills", {}).items():
        if isinstance(items, list):
            chunks.append({
                "section": "skills",
                "name": f"Skills — {category}",
                "text": f"Skill category: {category}\nTechnologies: {', '.join(items)}",
            })

    # FAQ — one chunk per Q&A pair
    for faq in data.get("faq", []):
        chunks.append({
            "section": "faq",
            "name": f"FAQ: {faq.get('q', '')}",
            "text": f"Question: {faq.get('q', '')}\nAnswer: {faq.get('a', '')}",
        })

    # Contact / social proof
    social = data.get("social_proof", {})
    chunks.append({
        "section": "contact",
        "name": "Contact & Links",
        "text": (
            f"Email: {social.get('email', '')}\n"
            f"Portfolio: {social.get('portfolio', '')}\n"
            f"GitHub: {social.get('github', '')}\n"
            f"LinkedIn: {social.get('linkedin', '')}\n"
            f"HuggingFace: {social.get('hf_spaces', '')}\n"
            f"HybridRAG demo: {social.get('hybridrag_demo', '')}"
        ),
    })

    return chunks


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def embed_text(text: str, retries: int = 3) -> list[float]:
    """Embed a single text string using Google text-embedding-004."""
    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    for attempt in range(retries):
        try:
            result = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text,
                config=genai_types.EmbedContentConfig(
                    task_type="retrieval_document",
                    output_dimensionality=VECTOR_DIM,
                ),
            )
            return result.embeddings[0].values
        except Exception as exc:
            if attempt < retries - 1 and ("429" in str(exc) or "quota" in str(exc).lower()):
                wait = 2 ** attempt
                print(f"  Rate limited, retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("Embedding failed after max retries")


# ---------------------------------------------------------------------------
# Qdrant
# ---------------------------------------------------------------------------

def get_qdrant_client() -> QdrantClient:
    return QdrantClient(
        url=os.environ["QDRANT_URL"],
        api_key=os.environ["QDRANT_API_KEY"],
    )


def ensure_collection(client: QdrantClient) -> None:
    if not client.collection_exists(COLLECTION):
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config=qdrant_models.VectorParams(
                size=VECTOR_DIM,
                distance=qdrant_models.Distance.COSINE,
            ),
        )
        print(f"Created collection '{COLLECTION}'")
    else:
        print(f"Collection '{COLLECTION}' already exists — will upsert")


def upsert_chunks(client: QdrantClient, chunks: list[dict]) -> None:
    points = []
    for idx, chunk in enumerate(chunks):
        point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"aria:{chunk['section']}:{chunk['name']}"))
        points.append(
            qdrant_models.PointStruct(
                id=point_id,
                vector=chunk["embedding"],
                payload={
                    "text": chunk["text"],
                    "section": chunk["section"],
                    "name": chunk["name"],
                    "chunk_index": idx,
                },
            )
        )
    client.upsert(collection_name=COLLECTION, points=points)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Validate env
    for var in ["GOOGLE_API_KEY", "QDRANT_URL", "QDRANT_API_KEY"]:
        if not os.environ.get(var):
            raise EnvironmentError(f"Missing required environment variable: {var}")

    print(f"Loading knowledge base from {DATA_PATH}...")
    with open(DATA_PATH) as f:
        data = json.load(f)

    chunks = build_chunks(data)
    print(f"Built {len(chunks)} chunks")

    print("Embedding chunks...")
    for i, chunk in enumerate(chunks):
        print(f"  [{i+1}/{len(chunks)}] {chunk['name'][:60]}")
        chunk["embedding"] = embed_text(chunk["text"])
        time.sleep(0.1)  # gentle rate limit

    print("Connecting to Qdrant Cloud...")
    client = get_qdrant_client()
    ensure_collection(client)

    print("Upserting to Qdrant...")
    upsert_chunks(client, chunks)

    print(f"\n✓ Ingested {len(chunks)} chunks into '{COLLECTION}'")


if __name__ == "__main__":
    main()
