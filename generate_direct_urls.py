# Pattern details (Derived from the working usercontent curl)
job_id = "200b2e41-9ad6-44d0-9a9a-321ede1de4d8"
timestamp = "20251227T203330Z"
batch = "3"
user_id = "726884942506"  # IMPORTANT: This is the user ID for usercontent.google.com links
total_files = 114

output_file = "/Users/greg/.gemini/antigravity/scratch/urls_direct.txt"

with open(output_file, "w") as f:
    for i in range(total_files):
        # i=0 -> part=001, i=113 -> part=114
        part_str = str(i + 1).zfill(3)
        url = f"https://takeout-download.usercontent.google.com/download/takeout-{timestamp}-{batch}-{part_str}.zip?j={job_id}&i={i}&user={user_id}&authuser=0"
        f.write(url + "\n")
        f.write(f"  out=takeout{i+1}.zip\n")

print(f"Generated {total_files} direct URLs in {output_file}")
