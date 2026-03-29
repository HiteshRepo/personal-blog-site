---
title: "Vector Databases, ANN, and Chunking: Storing Knowledge for Retrieval"
date: 2026-03-29T21:11:47-07:00
summary: "A practical guide for software engineers covering how vector databases use Approximate Nearest Neighbor algorithms to search millions of embeddings efficiently, and how to chunk documents intelligently so your RAG pipeline actually retrieves useful, precise context."
draft: false
ai_generated: true
tags: ["embeddings", "rag", "vector-database", "ann", "chunking", "nlp", "ai"]
categories: []
---

> **Note:** This post was AI-generated from rough notes using the blog generation workflow.

If you've been building a RAG pipeline, you've probably hit the point where you've embedded a few thousand documents and everything works great. Then you push toward 100,000 documents and suddenly your query latency tanks. This post is about two things that sit right in the middle of that scaling problem: how vector databases actually find relevant vectors fast, and how you split your documents into chunks that are worth retrieving in the first place.

## The Scale Problem with Brute Force Search

Let's say you've embedded 100,000 documents. Each embedding is a 1536-dimensional vector (standard for OpenAI's `text-embedding-ada-002`). A query comes in, you embed it, and now you need to find the most similar vectors in your store.

The naive approach: compute cosine similarity between the query vector and every single stored vector. That's 100,000 dot products across 1,536 dimensions. For a single query. At production load with concurrent users, this becomes a serious problem fast — O(n) per query, no way around it.

This is called **Exact Nearest Neighbor (ENN)** search. It's correct — you're guaranteed to find the actual closest vectors — but it doesn't scale. You need something smarter.

## ANN: Trade a Little Accuracy for a Lot of Speed

**Approximate Nearest Neighbor (ANN)** algorithms solve this by accepting a small, controlled accuracy trade-off in exchange for dramatically faster search. Instead of checking every vector, they use data structures that let you skip most of the search space and focus on the regions most likely to contain your answer.

In practice, for RAG use cases, this trade-off is essentially invisible. If your search returns 9 out of the 10 most relevant chunks instead of all 10, your LLM still has great context to work with. The accuracy loss rarely matters; the speed gain always does.

### How ANN Data Structures Work

Think of a library. If you wanted to find books about distributed systems, you wouldn't read every book on every shelf. You'd go to the computer science section, find the systems shelf, and scan from there. The library's organization *is* the index. ANN algorithms build that same kind of index for vectors.

Three main approaches:

**Clustering (e.g., IVF — Inverted File Index):** Group vectors into clusters at index-build time. When a query comes in, find the nearest cluster centroids first, then search only within those clusters. You skip the vast majority of your data.

**Graph-based (e.g., HNSW — Hierarchical Navigable Small World):** Each vector is a node in a graph, connected to its nearest neighbors. Searching means walking the graph — you start at an entry point and greedily hop to closer and closer neighbors. HNSW is the algorithm behind most high-performance vector DBs today.

**LSH — Locality Sensitive Hashing:** Similar vectors are hashed into the same bucket using specially designed hash functions. Search becomes a bucket lookup instead of an exhaustive scan. Less popular now but useful to know.

Here's a quick illustration of the ENN vs ANN difference in code:

```python
# Full code: https://github.com/HiteshRepo/ai-practice-projects/blob/main/embedding-and-rag/snippets/04_enn_vs_ann.py

import numpy as np
from sklearn.neighbors import NearestNeighbors
import faiss
import time

# ENN: brute force with sklearn
nn = NearestNeighbors(n_neighbors=5, metric='cosine', algorithm='brute')
nn.fit(embeddings)

start = time.time()
distances, indices = nn.kneighbors([query_vector])
print(f"ENN time: {time.time() - start:.4f}s")

# ANN: FAISS with IVF index
dimension = embeddings.shape[1]
quantizer = faiss.IndexFlatL2(dimension)
index = faiss.IndexIVFFlat(quantizer, dimension, nlist=100)
index.train(embeddings)
index.add(embeddings)

start = time.time()
distances, indices = index.search(np.array([query_vector]), k=5)
print(f"ANN time: {time.time() - start:.4f}s")
```

At 100k vectors the timing difference becomes obvious. At 10 million, ENN is simply not viable.

## Vector Databases in Production

You could manage FAISS indexes yourself, but production systems need persistence, filtering, metadata storage, and horizontal scaling. That's what vector databases give you.

The popular options right now:

- **Pinecone** — fully managed, minimal ops overhead, great for teams who want to skip infra
- **Weaviate** — open source, supports hybrid search (vector + keyword), strong schema model
- **Qdrant** — open source, Rust-based, excellent filtering capabilities alongside vector search
- **Chroma** — lightweight, great for local development and prototyping
- **pgvector** — Postgres extension; if your stack is already on Postgres, this is often the pragmatic choice

```python
# Full code: https://github.com/HiteshRepo/ai-practice-projects/blob/main/embedding-and-rag/snippets/03_vector_db.py

import chromadb

client = chromadb.Client()
collection = client.create_collection("docs")

collection.add(
    documents=["Transformers use self-attention mechanisms", "RAG combines retrieval with generation"],
    embeddings=[embedding_1, embedding_2],
    ids=["doc1", "doc2"],
    metadatas=[{"source": "paper.pdf", "page": 1}, {"source": "blog.md", "page": 1}]
)

results = collection.query(query_embeddings=[query_embedding], n_results=2)
```

Notice the `metadatas` field — we'll come back to why that matters.

## Chunking: Getting the Input Right

Even with a perfect vector database, your retrieval is only as good as what you put in. You can't embed an entire 50-page document as one vector. Embedding models have token limits (typically 512–8192 tokens depending on the model). More importantly, one giant vector loses specificity — asking "what's the refund policy?" shouldn't return a vector representing an entire terms-of-service document.

The goal of chunking: **small enough to be specific, large enough to carry context.** That's the Goldilocks problem of RAG.

### Chunking Strategies

**Fixed Size Chunking** is the simplest — split every N tokens or characters. Easy to implement, but it blindly cuts mid-sentence or mid-thought. The resulting chunks can be semantically broken.

**Fixed Size with Overlap** is an improvement. You repeat a window of tokens between adjacent chunks (e.g., 50-token overlap between 200-token chunks). This prevents hard context breaks at boundaries. Still not semantically aware though.

**Sentence / Paragraph Chunking** respects natural language structure — split on periods, newlines, or paragraph breaks. Better quality, but chunk sizes vary wildly. A paragraph can be 2 sentences or 20.

**Recursive Character Splitting** is what LangChain uses by default, and it's the practical sweet spot for most cases. It tries to split on paragraph boundaries first, then sentence boundaries, then word boundaries — working down a priority list until chunks fit within your size limit.

```python
# Full code: https://github.com/HiteshRepo/ai-practice-projects/blob/main/embedding-and-rag/snippets/05_chunking_strategies.py

from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", ". ", " ", ""]
)

chunks = splitter.split_text(document_text)
```

**Semantic Chunking** goes further — embed each sentence, then split where the embedding similarity drops below a threshold. You're grouping sentences by *meaning*, not just punctuation. Most accurate, but slowest to compute. Good for offline processing pipelines where quality matters more than indexing speed.

**Document-Aware / Structural Chunking** uses the document's own structure — headers, sections, subsections — as natural boundaries. If you're indexing Markdown docs, API references, or legal filings with clear structure, this is often the best approach. Parse the structure, use it.

### The Metadata Trick You Shouldn't Skip

Every chunk you store should carry metadata. Source file, page number, section heading, document date — whatever's relevant to your use case. Here's why: when you retrieve chunks and pass them to your LLM, you need to be able to cite where the answer came from. Without metadata, retrieved chunks are orphaned — you can't trace them back or show users a source.

```python
chunks_with_metadata = [
    {
        "text": chunk,
        "metadata": {
            "source": "employee_handbook.pdf",
            "page": page_number,
            "section": "Refund Policy",
            "chunk_index": i
        }
    }
    for i, chunk in enumerate(chunks)
]
```

This also enables filtered retrieval — "search only within documents tagged as `product: billing`" — which is a feature every serious vector DB supports.

## Bad Chunking Breaks Everything Downstream

This is worth saying plainly: bad chunking leads to bad retrieval, and bad retrieval leads to bad answers — even if you're running GPT-4 at the end of the pipeline. The LLM can only work with what you give it. If your chunks cut off context, mix unrelated topics, or are so large they're generic, your retrieval step will return noise instead of signal. Garbage in, garbage out applies here as much as anywhere in software.

## Wrapping Up

The infrastructure side of RAG isn't glamorous, but it's load-bearing. Getting vector search right means choosing an ANN-backed vector database appropriate for your scale and query patterns. Getting chunking right means thinking carefully about your document structure and what a "useful retrieval unit" actually looks like for your use case.

The full code examples for vector DB setup, ENN vs ANN comparison, and all chunking strategies are available at the [ai-practice-projects repo](https://github.com/HiteshRepo/ai-practice-projects/tree/main/embedding-and-rag/snippets). Start with `03_vector_db.py` to see Chroma in action, `04_enn_vs_ann.py` to benchmark the speed difference yourself, and `05_chunking_strategies.py` for runnable examples of every strategy covered here.
