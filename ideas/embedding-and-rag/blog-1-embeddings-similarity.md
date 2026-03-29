# Vector Embeddings & Similarity: The Foundation of RAG

- type: ai
- tags: embeddings, rag, vector-search, cosine-similarity, nlp, ai
- images: /images/embedding-and-rag/distance-metrics.png, /images/embedding-and-rag/distance-metrics-2.png, /images/embedding-and-rag/embedding-arrows.png
- A vector embedding is a list of numbers that represents the meaning of a piece of text — not the words themselves, but the underlying semantics
- Concrete example: "I love dogs" and "I adore puppies" have cosine similarity 0.68, while "I love dogs" and "Stock markets fell" have similarity 0.02 — numbers that match intuition about meaning
- Embedding models map text into a high-dimensional space (typically 768–1536 dimensions) where semantically similar texts land close together
- The key insight: direction matters more than magnitude — two vectors pointing the same way mean the same thing, even if one is longer
- Why not just subtract vectors? Because we care about direction, not size — verbose and terse descriptions of the same concept differ in magnitude but share direction
- Cosine similarity measures the angle between two vectors: 0° = identical meaning (1.0), 90° = unrelated (0.0), 180° = opposite meaning (-1.0)
- Cosine similarity formula: cos(θ) = (A · B) / (|A| × |B|) — dot product of the two vectors divided by the product of their magnitudes
- Step-by-step intuition: "The dog ran" and "A canine was running" point in nearly the same direction in embedding space despite sharing zero words
- Distance metrics comparison: Cosine similarity (direction-focused, scale-invariant), Euclidean distance (magnitude-sensitive, works for normalized vectors), Dot product (combines magnitude and angle — used in some retrieval systems)
- Real-world numbers: similarity between "I love dogs" and "I love dogs" = 1.0000, "I love dogs" and "I adore puppies" = 0.6831, "I love dogs" and "Stock markets fell" = 0.0197
- In RAG systems, cosine similarity is used to compare a user's query vector against every stored document vector to find the most relevant chunks
- Why this matters for RAG: the entire retrieval step depends on this similarity score being accurate — bad embeddings produce irrelevant retrievals regardless of how good the LLM is
- Demo code: https://github.com/HiteshRepo/ai-practice-projects/blob/main/embedding-and-rag/snippets/01_cosine_similarity.py and 02_why_cosine.py
