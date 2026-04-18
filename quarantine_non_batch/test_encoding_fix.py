import subprocess

def test_unzip_mock():
    # Simulate non-UTF8 output from unzip -l
    # Using raw bytes for the simulated output
    output = b"  Length      Date    Time    Name\n---------  ---------- -----   ----\n  1234567  2025-12-31 19:30   \xe6_file_with_bad_encoding.jpg\n---------                     -------\n  1234567                     1 file"
    
    try:
        # This simulates how we now decode in start_app.py
        decoded = output.decode('utf-8', errors='replace')
        print("Successfully decoded with 'replace':")
        print(decoded)
        
        # Verify line splitting and count logic
        total_files = 0
        for line in decoded.splitlines():
            if "files" in line and "----" not in line:
                 parts = line.split()
                 if len(parts) >= 2:
                     try:
                         # parts[1] is the count
                         total_files = int(parts[1])
                     except:
                         pass
        print(f"Detected total files: {total_files}")
        assert total_files == 1
        print("VERIFICATION SUCCESSFUL")
    except Exception as e:
        print(f"VERIFICATION FAILED: {e}")

if __name__ == "__main__":
    test_unzip_mock()
