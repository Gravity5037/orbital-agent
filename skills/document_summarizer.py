"""
ORBITAL OS AUTO-LEARNED SKILL: Document Keyword Extractor
"""
import re
from collections import Counter

NAME = "Document Keyword Extractor"
DESCRIPTION = "Extracts top keywords, frequencies, and structure from text."
KEYWORDS = ["summarize", "keywords", "extract keywords", "word count"]

def run(prompt: str) -> str:
    text = prompt.replace("summarize", "").replace("extract keywords", "").strip()
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    if not words:
        return "[Extractor] Text too short to extract keywords."
    stopwords = {"the", "and", "for", "with", "that", "this", "from", "are", "was"}
    filtered = [w for w in words if w not in stopwords]
    counts = Counter(filtered).most_common(5)
    formatted = ", ".join([f"{w} ({c}x)" for w, c in counts])
    return f"[Keyword Analysis | {len(words)} total words]: Top keywords: {formatted}"

if __name__ == "__main__":
    print(run("Orbital OS is an autonomous cognitive AI operating system for desktop."))
