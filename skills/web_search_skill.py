"""
ORBITAL OS - Web Search & Live Research Skill
Allows Orbital to query the internet in real-time, retrieve documentation,
and answer queries with current information.
"""

import sys
import os

sys.path.append(r"C:\Orbital\core")
try:
    from web_researcher import web_researcher
except Exception:
    web_researcher = None

NAME = "Live Web Research"
DESCRIPTION = "Searches the internet in real-time and fact-checks information"
KEYWORDS = [
    "search the web", "search for", "look up", "research online",
    "what is the latest", "who is", "latest news on", "find online"
]

def run(prompt: str) -> str:
    if not web_researcher:
        return "[Web Search Skill] Web researcher module offline."

    # Extract clean query
    clean_query = prompt
    for trigger in ["search the web for", "search for", "look up", "research online"]:
        if trigger in clean_query.lower():
            clean_query = clean_query.lower().split(trigger, 1)[-1].strip()
            break

    results = web_researcher.search_duckduckgo(clean_query, max_results=3)
    if not results:
        return f"[Live Web Search] No immediate results returned for: '{clean_query}'"

    formatted = [f"[WEB] [Live Web Research Results for: '{clean_query}']\n"]
    for i, r in enumerate(results, 1):
        formatted.append(f"{i}. {r['snippet']}")
        if r.get('source') and r['source'] != 'N/A':
            formatted.append(f"   Source: {r['source']}")
        formatted.append("")

    return "\n".join(formatted).strip()

if __name__ == "__main__":
    print(run("search for latest Python version"))
