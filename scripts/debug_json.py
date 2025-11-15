import re
import json
from pathlib import Path

html = Path("knowledge/chatgpt/chatgpt chatlog 11-9-25.html").read_text(encoding="utf-8")
match = re.search(r"var jsonData = (\[.*?\]);", html, re.S)
text = match.group(1)

pattern = re.compile(r"\\(?![\"\\/bfnrt]|u[0-9a-fA-F]{4})")
sanitized = text
while True:
    sanitized, count = pattern.subn(r"\\\\", sanitized)
    if count == 0:
        break

try:
    data = json.loads(sanitized)
    print("Parsed conversations:", len(data))
    print("First title:", data[0]["title"])
except json.JSONDecodeError as exc:
    print("Still failing:", exc)
    pos = exc.pos
    print("Context:", sanitized[pos - 50 : pos + 50])

