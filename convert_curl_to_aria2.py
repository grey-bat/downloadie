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

# Update URLs (Use the direct ones already generated)
urls_input_path = "/Users/greg/.gemini/antigravity/scratch/urls_direct.txt"
urls_output_path = urls_input_path # Already direct

# Build aria2c command
aria2_cmd = ["aria2c"]
aria2_cmd.append(f"-i {urls_input_path}") # Input file with direct links
aria2_cmd.append("-d /Volumes/Backup/photos") # Output dir
aria2_cmd.append("-j 16") # 16 parallel downloads
aria2_cmd.append("-x 16") # 16 connections per file
aria2_cmd.append("-s 16") # 16 split per file
aria2_cmd.append("--min-split-size=1M")
aria2_cmd.append("-c") # Continue
aria2_cmd.append("--file-allocation=none")
aria2_cmd.append("--retry-wait=10")
aria2_cmd.append("--max-tries=0")
aria2_cmd.append("--summary-interval=60")
aria2_cmd.append("--log=aria2.log")
aria2_cmd.append("--log-level=notice")

# Add headers
for h in headers:
    # aria2c syntax: --header="HeaderName: Value"
    # Need to escape double quotes for shell: " -> \"
    safe_h = h.replace('"', '\\"')
    aria2_cmd.append(f'--header="{safe_h}"')

# Add Cookie as header
if cookie_data:
    aria2_cmd.append(f'--header="Cookie: {cookie_data}"')

# Join into a shell script string
script_content = "#!/bin/bash\n" + " \\\n  ".join(aria2_cmd) + "\n"

with open('/Users/greg/.gemini/antigravity/scratch/download_takeout_aria2.sh', 'w') as f:
    f.write(script_content)

print("Created download_takeout_aria2.sh")
