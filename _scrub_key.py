"""Helper: strip hardcoded Groq API key from llm_engine.py during git filter-branch."""
import re
from pathlib import Path

target = Path("llm_engine.py")
if target.exists():
    original = target.read_text(encoding="utf-8", errors="replace")
    cleaned = re.sub(r'gsk_[A-Za-z0-9]{50,}', "YOUR_GROQ_API_KEY_HERE", original)
    if cleaned != original:
        target.write_text(cleaned, encoding="utf-8")
        print("Scrubbed llm_engine.py")
    else:
        print("No key found in llm_engine.py")
