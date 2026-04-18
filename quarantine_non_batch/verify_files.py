import os
import sys

def verify_zip(filepath):
    if not os.path.exists(filepath):
        return False, "File does not exist"
    
    try:
        with open(filepath, 'rb') as f:
            header = f.read(4)
            if header == b'PK\x03\x04':
                return True, "Valid ZIP header"
            else:
                return False, f"Invalid header: {header.hex()}"
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 verify_files.py <file1> <file2> ...")
        sys.exit(1)
    
    for path in sys.argv[1:]:
        valid, msg = verify_zip(path)
        status = "[PASS]" if valid else "[FAIL]"
        print(f"{status} {os.path.basename(path)}: {msg}")
