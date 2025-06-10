---
title: '{{ replace .File.ContentBaseName "-" " " | title }}'
date: {{ .Date }}
summary: "A brief summary of your post (1-2 sentences)"
tags: ["tag1", "tag2"]
draft: true
---

# {{ replace .File.ContentBaseName "-" " " | title }}

Write your content here. You can use Markdown formatting:

## Headings

### Sub-headings

**Bold text** and *italic text*

- Bullet points
- Another point

1. Numbered list
2. Second item

[Links](https://example.com)

![Images](/images/example.png)

```go
// Code blocks
func example() {
    fmt.Println("Hello, world!")
}
```

> Blockquotes for important notes or quotes

---

## Share This Post

[Share on Twitter](https://twitter.com/intent/tweet?text=I%20just%20read%20this%20great%20blog%20post!%20Check%20it%20out:%20[URL])  
[Share on LinkedIn](<https://www.linkedin.com/shareArticle?mini=true&url=[URL]&title={{> replace .File.ContentBaseName "-" " " | title }})
