import pypandoc
import os

def ensure_pandoc():
    try:
        pypandoc.get_pandoc_version()
    except OSError:
        print("[INFO] Pandoc not found. Downloading...")
        pypandoc.download_pandoc()
        print("[INFO] Pandoc installed successfully!")

ensure_pandoc()
