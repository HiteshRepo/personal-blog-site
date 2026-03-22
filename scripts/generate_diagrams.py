#!/usr/bin/env python3
"""Generate diagram PNGs for blog posts.

Source images are copied from  ideas/<subdir>/
Generated images are written to static/images/<subdir>/
The subdir is derived from the image path declared in the ideas file
(e.g. /images/llm-foundation/foo.png  →  subdir = llm-foundation).

Usage:
    # Generate ALL diagrams (first-time setup or full refresh)
    python3 scripts/generate_diagrams.py

    # Generate only diagrams needed for a specific ideas file
    python3 scripts/generate_diagrams.py ideas/llm-foundation/blog-1-rnn-era-qkv.md

    # Generate for multiple ideas files at once
    python3 scripts/generate_diagrams.py ideas/llm-foundation/blog-1-rnn-era-qkv.md ideas/ai-prompting-techniques/blog.md

Via make:
    make diagrams                                                    # all
    make diagrams FILE=ideas/llm-foundation/blog-1-rnn-era-qkv.md   # targeted
"""

import re
import shutil
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

IDEAS_DIR = Path("ideas")
STATIC_IMAGES_DIR = Path("static/images")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_dirs_for_image(img_path: str):
    """Return (source_dir, output_dir) derived from an image path.

    e.g. /images/llm-foundation/foo.png
         → ideas/llm-foundation/, static/images/llm-foundation/
    """
    parts = Path(img_path).parts
    # Expected: ('/', 'images', '<subdir>', 'filename.png')
    if len(parts) >= 3 and parts[1] == "images":
        subdir = parts[2]
    else:
        subdir = Path(img_path).parent.name or "llm-foundation"
    return IDEAS_DIR / subdir, STATIC_IMAGES_DIR / subdir


# ---------------------------------------------------------------------------
# Diagram generators  (each accepts output_dir so they're portable)
# Register new generators in GENERATORS at the bottom of this file.
# ---------------------------------------------------------------------------

def plot_softmax_weights(output_dir: Path):
    words = ["The", "dog", "barked"]
    weights = [0.07, 0.90, 0.03]
    colors = ["#5b9bd5", "#ff7043", "#5b9bd5"]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(words, weights, color=colors, width=0.45, edgecolor="white", linewidth=1.5)

    for bar, w in zip(bars, weights):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{w:.0%}",
            ha="center", va="bottom", fontsize=14, fontweight="bold",
        )

    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Attention weight", fontsize=12)
    ax.set_title(
        'Softmax attention weights for "barked"\n— which words does it attend to?',
        fontsize=13,
    )
    ax.set_facecolor("#f8f9fa")
    fig.patch.set_facecolor("white")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(labelsize=13)

    plt.tight_layout()
    _save("softmax-weights.png", output_dir)


def plot_scaling_comparison(output_dir: Path):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))

    scenarios = [
        {"title": "Small  d_k = 4\n÷ √4 = ÷2", "raw": 10, "scaled": 5, "color": "#5b9bd5"},
        {"title": "Large  d_k = 100\n÷ √100 = ÷10", "raw": 250, "scaled": 25, "color": "#ff7043"},
    ]

    for ax, s in zip(axes, scenarios):
        labels = ["Raw score", "Scaled score"]
        values = [s["raw"], s["scaled"]]
        bar_colors = [s["color"], "#4caf50"]
        bars = ax.bar(labels, values, color=bar_colors, width=0.45, edgecolor="white", linewidth=1.5)

        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + s["raw"] * 0.025,
                str(int(val)),
                ha="center", va="bottom", fontsize=14, fontweight="bold",
            )

        ax.set_title(s["title"], fontsize=12)
        ax.set_ylim(0, s["raw"] * 1.25)
        ax.set_facecolor("#f8f9fa")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(labelsize=11)

    fig.suptitle(
        "Why scale by 1/√d_k ?\n"
        "Large dimensions blow up dot-product scores → softmax saturates → gradients vanish",
        fontsize=12, fontweight="bold",
    )
    fig.patch.set_facecolor("white")
    plt.tight_layout()
    _save("scaling-comparison.png", output_dir)


def plot_positional_encoding(output_dir: Path):
    positions = np.arange(0, 60)
    d_model = 512

    series = [
        (0,  "sin", "#5b9bd5", "dim 0 (sin)"),
        (1,  "cos", "#ff7043", "dim 1 (cos)"),
        (10, "sin", "#4caf50", "dim 10 (sin)"),
        (50, "cos", "#ab47bc", "dim 50 (cos)"),
    ]

    fig, axes = plt.subplots(2, 1, figsize=(11, 5.5), sharex=True)

    for i, (dim, fn, color, label) in enumerate(series):
        enc = (
            np.sin(positions / (10000 ** (2 * dim / d_model)))
            if fn == "sin"
            else np.cos(positions / (10000 ** (2 * dim / d_model)))
        )
        ax = axes[0] if i < 2 else axes[1]
        ax.plot(positions, enc, label=label, color=color, linewidth=2)

    axes[0].set_title(
        "Positional Encoding — each dimension oscillates at a different frequency\n"
        "so the model can distinguish every position uniquely",
        fontsize=12,
    )
    axes[1].set_xlabel("Position in sequence", fontsize=11)

    for ax in axes:
        ax.set_ylabel("Encoding value", fontsize=10)
        ax.set_facecolor("#f8f9fa")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.axhline(0, color="gray", linewidth=0.5, linestyle="--")
        ax.legend(fontsize=9, loc="upper right")
        ax.set_ylim(-1.2, 1.2)

    fig.patch.set_facecolor("white")
    plt.tight_layout()
    _save("positional-encoding.png", output_dir)


def plot_masking_matrix(output_dir: Path):
    labels = ["<start>", "The", "dog", "barked", "loudly", "<end>"]
    n = len(labels)
    mask = np.tril(np.ones((n, n)))

    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    ax.imshow(mask, cmap="Blues", vmin=0, vmax=1.3, aspect="equal")

    for i in range(n):
        for j in range(n):
            symbol = "✓" if mask[i, j] else "✗"
            color = "white" if mask[i, j] else "#cc3333"
            ax.text(j, i, symbol, ha="center", va="center",
                    fontsize=16, color=color, fontweight="bold")

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=10)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Can attend TO  →", fontsize=11)
    ax.set_ylabel("←  Token being predicted", fontsize=11)
    ax.set_title(
        "Decoder Masked Self-Attention\n"
        "each token can only attend to itself and earlier tokens",
        fontsize=12,
    )
    fig.patch.set_facecolor("white")
    plt.tight_layout()
    _save("masking-matrix.png", output_dir)


# ---------------------------------------------------------------------------
# Registry — add new generators here as {filename: function}
# ---------------------------------------------------------------------------

GENERATORS = {
    "softmax-weights.png":     plot_softmax_weights,
    "scaling-comparison.png":  plot_scaling_comparison,
    "positional-encoding.png": plot_positional_encoding,
    "masking-matrix.png":      plot_masking_matrix,
}


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def get_images_from_ideas_file(filepath: str):
    """Return image paths declared in a `- images:` bullet."""
    content = Path(filepath).read_text()
    for line in content.strip().split("\n"):
        stripped = line.strip()
        if re.match(r"^[-*]\s+images\s*:", stripped, re.IGNORECASE):
            images_str = stripped.split(":", 1)[1].strip()
            return [i.strip() for i in images_str.split(",") if i.strip()]
    return []


def process_image(img_path: str):
    """Copy or generate a single image based on its declared path."""
    source_dir, output_dir = get_dirs_for_image(img_path)
    filename = Path(img_path).name
    output_dir.mkdir(parents=True, exist_ok=True)

    if filename in GENERATORS:
        GENERATORS[filename](output_dir)
        return

    src = source_dir / filename
    if src.exists():
        shutil.copy2(src, output_dir / filename)
        print(f"  copied  {filename}")
    else:
        print(f"  WARNING: no generator or source file found for {filename}")
        print(f"           looked in {source_dir}")


def run_targeted(ideas_files):
    seen = set()
    for f in ideas_files:
        print(f"\nScanning {f} …")
        images = get_images_from_ideas_file(f)
        if not images:
            print("  (no images declared)")
            continue
        for img_path in images:
            filename = Path(img_path).name
            if filename not in seen:
                process_image(img_path)
                seen.add(filename)


def run_all():
    # Copy all PNGs from every ideas/* subdirectory
    print("Copying existing images from all ideas subdirectories …")
    for subdir in sorted(IDEAS_DIR.iterdir()):
        if not subdir.is_dir():
            continue
        pngs = sorted(subdir.glob("*.png"))
        if not pngs:
            continue
        output_dir = STATIC_IMAGES_DIR / subdir.name
        output_dir.mkdir(parents=True, exist_ok=True)
        for img in pngs:
            shutil.copy2(img, output_dir / img.name)
            print(f"  copied  {subdir.name}/{img.name}")

    # Run all programmatic generators into their target directories
    print("\nGenerating all programmatic diagrams …")
    for filename, fn in GENERATORS.items():
        # Derive the output dir from the generator's registered filename
        # All current generators belong to llm-foundation
        output_dir = STATIC_IMAGES_DIR / "llm-foundation"
        output_dir.mkdir(parents=True, exist_ok=True)
        fn(output_dir)


def _save(filename: str, output_dir: Path):
    out = output_dir / filename
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  created {filename}")


def main():
    if len(sys.argv) > 1:
        run_targeted(sys.argv[1:])
    else:
        run_all()

    print(f"\nDone. Assets in {STATIC_IMAGES_DIR}/")


if __name__ == "__main__":
    main()
