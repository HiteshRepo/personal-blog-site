# Training for Greatness: Speed, BLEU Records, and the Multimodal Vision

- type: ai
- tags: transformers, training, benchmarks, bleu, nlp, multimodal, llm, attention
- Training dataset: WMT 2014 English-German (4.5M sentence pairs) and English-French (36M sentence pairs)
- Base Transformer trained in just 12 hours on 8 NVIDIA P100 GPUs — a fraction of the cost of previous models
- Big Transformer trained in 3.5 days on 8 P100 GPUs; competing ConvS2S took 9.5 days; GNMT ensemble took ~6 weeks
- English-to-German BLEU: 28.4 — new state of the art, beating the previous best by more than 2.0 BLEU points
- English-to-French BLEU: 41.0 — a single Transformer model outperformed all previous ensemble models
- Training techniques: Adam optimizer, dropout (P=0.1), label smoothing (epsilon=0.1) to prevent overconfidence
- Inference: beam search with beam size 4 and length penalty alpha=0.6 to balance length
- Architecture generalized beyond translation — tested on English constituency parsing and still achieved competitive results
- Authors' multimodal vision: apply Transformers to images, audio, and video — "attention is all you need" extends beyond text
- Plan for large inputs: restrict attention to local neighborhoods of the input/output to handle very long sequences efficiently
- The paper's closing words: "We are excited about the future of attention-based models"
- The legacy: Transformers directly inspired BERT (2018), GPT-1 (2018), and every major LLM that followed
- The fundamental shift: from task-specific sequential architectures to a single general-purpose, fully parallelizable model
- Why this mattered financially: training cost dropped by an order of magnitude, making frontier NLP accessible to smaller teams
- Key insight for practitioners: the Transformer's quality comes from its ability to model relationships across the entire sequence simultaneously — not from deeper networks or more data alone
