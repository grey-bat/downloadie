import os
import re

curl_cmd_path = '/Users/greg/.gemini/antigravity/scratch/curl_command.txt'
output_path = '/Users/greg/.gemini/antigravity/scratch/cookies.txt'

try:
    with open(curl_cmd_path, 'r') as f:
        content = f.read()
except FileNotFoundError:
    print("Curl command file not found.")
    exit(1)

# Extract cookie string from -b '...'
match = re.search(r"-b '([^']+)'", content)
if not match:
    print("No cookie string found in curl command.")
    exit(1)

cookie_str = match.group(1)
cookies = cookie_str.split("; ")

# Netscape format: domain, tailmatch, path, secure, expires, name, value
# We assume .google.com and / for all.
netscape_lines = ["# Netscape HTTP Cookie File\n"]

for c in cookies:
    if "=" not in c: continue
    name, val = c.split("=", 1)
    # domain, tailmatch, path, secure, expires, name, value
    line = f".google.com\tTRUE\t/\tTRUE\t0\t{name}\t{val}\n"
    netscape_lines.append(line)

with open(output_path, 'w') as f:
    f.writelines(netscape_lines)

print(f"Created Netscape cookies.txt with {len(cookies)} cookies.")
