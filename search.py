import os
import sys

def search_files(query, directory):
    for root, _, files in os.walk(directory):
        if 'node_modules' in root or '.git' in root or '.venv' in root:
            continue
        for file in files:
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if query.lower() in line.lower():
                            print(f"{path}:{i+1}: {line.strip()}".encode('utf-8', 'replace').decode('utf-8'))
            except UnicodeDecodeError:
                pass

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python search.py <query> <directory>")
        sys.exit(1)
    
    # reconfigure stdout to utf-8
    sys.stdout.reconfigure(encoding='utf-8')
    search_files(sys.argv[1], sys.argv[2])
