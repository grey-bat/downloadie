import re

curl_cmd_path = '/Users/greg/.gemini/antigravity/scratch/curl_command.txt'
try:
    with open(curl_cmd_path, 'r') as f:
        content = f.read()
except FileNotFoundError:
    print("Curl command file not found.")
    exit(1)

# Extract headers
headers = re.findall(r"-H '([^']+)'", content)
# Extract cookie if it's passed with -b
cookies_match = re.search(r"-b '([^']+)'", content)
cookie_data = cookies_match.group(1) if cookies_match else None

# Update URLs (Use the robust redirector links)
urls_input_path = "/Users/greg/.gemini/antigravity/scratch/urls.txt"
urls_output_path = "/Users/greg/.gemini/antigravity/scratch/urls_with_rapt.txt"

# Extract rapt token from curl command URL
rapt_match = re.search(r"[?&]rapt=([^&']+)", content)
rapt_token = rapt_match.group(1) if rapt_match else ""

with open(urls_input_path, 'r') as f:
    urls = f.read().splitlines()

with open(urls_output_path, 'w') as f:
    for url in urls:
        # Ensure we use the correct account ID (Gaia ID)
        # Append rapt for authorization
        if rapt_token and 'rapt=' not in url:
            url += f"&rapt={rapt_token}"
        f.write(url + "\n")

# Build aria2c command
aria2_cmd = ["aria2c"]
aria2_cmd.append(f"-i {urls_output_path}") # Input file with rapt and GAIA ID links
aria2_cmd.append("-d /Volumes/Backup/photos") # Output dir
aria2_cmd.append("-j 3") # Match Google's 3-concurrent limit for stability
aria2_cmd.append("-x 16") # 16 connections per file
aria2_cmd.append("-s 16") # 16 splits per file
aria2_cmd.append("--stream-piece-selector=random")
aria2_cmd.append("--min-split-size=1M")
aria2_cmd.append("--connect-timeout=10")
aria2_cmd.append("--timeout=30")
aria2_cmd.append("-c") # Continue
aria2_cmd.append("--file-allocation=prealloc") # prealloc might be faster on some drives
aria2_cmd.append("--retry-wait=5")
aria2_cmd.append("--max-tries=0")
aria2_cmd.append("--summary-interval=30")
aria2_cmd.append("--log=aria2.log")
aria2_cmd.append("--log-level=notice") # Notice level includes redirects

aria2_cmd.append("--load-cookies=/Users/greg/.gemini/antigravity/scratch/cookies.txt")

# Add headers (Filtered)
for h in headers:
    # Skip cookie header as it's handled by --load-cookies
    if h.lower().startswith("cookie:"): continue
    
    # aria2c syntax: --header="HeaderName: Value"
    safe_h = h.replace('"', '\\"')
    aria2_cmd.append(f'--header="{safe_h}"')

# Join into a shell script string
script_content = "#!/bin/bash\n" + " \\\n  ".join(aria2_cmd) + "\n"

with open('/Users/greg/.gemini/antigravity/scratch/download_takeout_aria2.sh', 'w') as f:
    f.write(script_content)

print("Created download_takeout_aria2.sh")
