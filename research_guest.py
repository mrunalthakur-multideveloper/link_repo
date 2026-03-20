import requests
import re
from urllib.parse import unquote

url = "https://www.linkedin.com/jobs/view/4387638757"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

print(f"--- Fetching {url} as Guest ---")
resp = requests.get(url, headers=headers, timeout=10)
html = resp.text

# 1. Look for ALL https URLs
print(f"HTML length: {len(html)}")
all_urls = re.findall(r'https?://[a-zA-Z0-9.\-_/=%&?#]+', html)

external = []
for u in all_urls:
    u = unquote(u).lower()
    if 'linkedin.com' not in u and 'static.licdn.com' not in u and 'media.licdn.com' not in u:
        external.append(u)

print(f"Found {len(external)} unique external URLs:")
unique_ext = sorted(list(set(external)))
for u in unique_ext[:50]:
    print(f"  {u[:100]}")

# 2. Look for offsiteApplyUrl anywhere
it = re.finditer(r'offsiteApplyUrl', html)
for match in it:
    print(f"Found 'offsiteApplyUrl' at position {match.start()}!")
    snippet = html[match.start():match.start()+500]
    print(f"Snippet: {snippet}")

with open("guest_view_asml.html", "w", encoding="utf-8") as f:
    f.write(html)
