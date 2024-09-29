---
title: 'N-Grams Uncovered: A Key Component of Large Language Models'
date: 2024-09-29
summary: 'Decoding N-Grams: The Heart of Large Language Models'
tags: ["ai", "machine learning", "tech", "LLMs", "AI resources", "n-grams", "transformer"]
---

# Understanding LLMs: How Large Language Models Use Auto-Completion to Predict Text

## Why Am I Writing This Blog Post?

- [Why](../first-ai-post/) am I writing this blog post?
- [Where](../) do I find all the relevant blogs on AI grouped together?

---

Alright, folks! For this blog post and the upcoming ones, let’s think of **Large Language Models (LLMs)** as your friendly neighborhood *auto-complete* feature. You know, that delightful little tool that pops up suggestions when you start typing in your browser? Isn’t it fascinating how it guesses what you’re about to say next? 

But how does it do that? *Cue the suspenseful music...*

## The Art of Guessing in AI

Before diving into the *how*, let’s establish one thing: **auto-complete is basically guessing**. And guess what? We can all play this guessing game too! But here’s the catch—we don’t just throw words at random; we base our guesses on something. In the world of **LLMs** and AI, that something is called **context**. Sounds fancy, right? 

So, what does this “context” mean? It means that any tool, be it an AI or your chatty friend, uses the previously typed words or sentences to predict the next most probable words. 

### What Do I Mean by “Most Probable Words”?

Why don’t I just say “words”? Well, because there’s a plethora of possibilities! For example, if your previous words are “I love,” the next guesses could be:

- Dogs
- Cats
- Trees
- …and my personal favorite, **Artificial Intelligence!**

Now, if your previous words are “I love artificial,” the next guesses might include:

- Intelligence
- Plants
- Water bodies
- …and maybe even “my new robot vacuum cleaner” (we can dream!).

### How Do These Guesses Appear?

Ah, now we’re getting to the juicy part! Let’s say they refer to a **lookup table**. This table contains all the word mappings. For the word “I,” it might have multiple matches like “love,” “like,” and “am.” Each of these matches comes with a weight. The words are displayed in decreasing order of their weights—think of it as a popularity contest where the most popular words get all the spotlight.

### Where Did This Lookup Table Come From?

*Drumroll, please!* This magic table is called a **training corpus**. It’s not just a simple table; it’s a collection of all publicly available data. The LLMs train on this data to build their lookup tables.

And just to clarify, the weights are assigned based on how frequently these word combinations occur. For example, if “I love” pops up more often than “I like” in the training data, the model will prioritize “love” when we type “I.”

### But Wait, There’s More!

You might be wondering, “How can I make it choose the 2nd or 3rd most probable guess instead of just the top one?” Well, hold on to your hats! We can achieve this by tweaking something called the **temperature parameter**. We’ll dive deeper into that in a future blog post (yep, consider this your little teaser!).

For now, just remember: **temperature governs the ‘creativity’ of the LLM model.** 

## LLMs: Auto-Complete on Steroids!

So, in essence, LLMs can be referred to as **auto-complete on steroids**. But wait, you might be thinking, “What do you mean by the ‘base model’?” Yes, my friend, there are other models! Just like we have versions of our favorite apps, LLMs also have various models based on their capabilities. We’ll explore these in future posts. 

## Understanding N-Grams and Their Role in Text Prediction

Ah, yes! We’ve been dancing around the topic of **N-grams**. My apologies for the *contextual detour*!

N-grams are sequences of “n” words or tokens used in text analysis. Here’s the breakdown:

- **2-gram (bigram)**: A sequence of 2 words (e.g., “machine learning”).
- **3-gram (trigram)**: A sequence of 3 words (e.g., “artificial neural networks”).
- **4-gram, 5-gram, etc.**: Sequences of 4, 5, or more words (e.g., “large language models are”).

In general, N-grams help in analyzing patterns and context in language. The larger the “n,” the more words or tokens you’re considering.

### Example of N-grams

Take the phrase, “I love artificial intelligence.” 

- **1-gram (unigram)**: Each word individually: `["I", "love", "artificial", "intelligence"]`
- **2-gram (bigram)**: Pairs of two words: `["I love", "love artificial", "artificial intelligence"]`
- **3-gram (trigram)**: Groups of three words: `["I love artificial", "love artificial intelligence"]`
- **4-gram**: Groups of four words: `["I love artificial intelligence"]`

The more words you combine (higher N), the more specific the context becomes. For instance, “artificial intelligence” as a 2-gram holds more meaning together than just “artificial” and “intelligence” as separate words. 

## Why Are LLMs More Advanced?

Base model LLMs predict the next word based on context. However, they don’t rely strictly on N-grams (fixed sequences of words). Instead, LLMs use a more advanced approach: they learn patterns and relationships across entire sentences and beyond. This means they draw context from long stretches of text, not just a specific number of preceding words.

So, while N-grams capture short-term context, LLMs consider much broader and deeper context for better predictions.

### Let’s Get Technical!

Unlike your browser, which uses only the first few words as context to suggest the next words, LLMs use a wealth of context (possibly *thousands of grams*) to make predictions. We’ve seen how ChatGPT interacts with us based on historical conversations in a single chat—now that’s some serious memory!

Predicting the next word using a thousand-gram sequence would be incredibly compute-intensive if done purely with N-grams. The model would need to store and process a massive number of possible sequences, which would quickly become impractical as the sequence length increases.

However, large language models (LLMs) don’t directly rely on such long N-gram sequences. Instead, they use techniques like **transformers**, which allow them to handle long-range dependencies more efficiently. Transformers employ attention mechanisms to focus on the most relevant parts of the context, making it much more efficient than trying to manage thousand-gram sequences through brute force.

---

And with that, dear readers, we’ll wrap up this blog post!

Stay tuned to explore the world of **transformers** in our next exciting adventure! 

---

## Join the Conversation!

If you found this blog post helpful, please leave a comment below or share it with your friends! For more insights into AI and machine learning, don’t forget to check out my other posts.

### Share This Post!
If you found this post helpful or entertaining, please share it with your friends!

[Share on Twitter](https://twitter.com/intent/tweet?text=I%20just%20read%20this%20great%20blog%20about%20AI%20and%20LLMs!%20Check%20it%20out:%20[https://hitesh-pattanayak.netlify.app/technical/ai/n-grams/])  
[Share on Facebook](https://www.facebook.com/sharer/sharer.php?u=[https://hitesh-pattanayak.netlify.app/technical/ai/n-grams/])  
[Share on LinkedIn](https://www.linkedin.com/shareArticle?mini=true&url=[https://hitesh-pattanayak.netlify.app/technical/ai/n-grams/]&title=Adventures%20in%20AI:%20My%20Journey%20into%20the%20World%20of%20LLMs&summary=Why%20am%20I%20writing%20these%20AI%20blogs?&source=)  
[Share on Reddit](https://reddit.com/submit?url=[https://hitesh-pattanayak.netlify.app/technical/ai/n-grams/]&title=Adventures%20in%20AI:%20My%20Journey%20into%20the%20World%20of%20LLMs)  

