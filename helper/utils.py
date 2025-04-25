# +++ Made By Obito [telegram username: @i_killed_my_clan] +++ #
import re
import os
import zipfile
import shutil
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
import ebooklib
from ebooklib import epub

def natural_sort(file_list):
    return sorted(file_list, key=lambda f: [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', f)])

def remove_duplicates(file_list):
    base_map = {}
    valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".img")
    for file in file_list:
        name, ext = os.path.splitext(os.path.basename(file))
        if ext.lower() not in valid_extensions:
            continue
        match = re.match(r"^(\d+)[a-zA-Z]?$", name)
        if match:
            base = match.group(1)
            if base not in base_map or not name.endswith("t"):
                base_map[base] = file
    return list(base_map.values())

def create_banner_pdf(banner_image_path: str, url: str = None) -> str:
    temp_dir = tempfile.mkdtemp()
    output_path = os.path.join(temp_dir, "banner.pdf")
    c = canvas.Canvas(output_path, pagesize=letter)
    if banner_image_path and os.path.exists(banner_image_path):
        img = Image.open(banner_image_path)
        img_width, img_height = img.size
        aspect = img_height / float(img_width)
        target_width = letter[0] - 40
        target_height = target_width * aspect
        c.drawImage(banner_image_path, 20, letter[1] - target_height - 20, target_width, target_height)
    if url:
        c.linkAbsolute("", url, (20, letter[1] - target_height - 20, 20 + target_width, letter[1] - 20))
    c.showPage()
    c.save()
    return output_path

def add_banner_to_pdf(input_pdf: str, output_pdf: str, banner_pdf: str, position: str):
    reader = PdfReader(input_pdf)
    banner_reader = PdfReader(banner_pdf)
    writer = PdfWriter()
    if position in ["first", "both"]:
        writer.add_page(banner_reader.pages[0])
    for page in reader.pages:
        writer.add_page(page)
    if position in ["last", "both"]:
        writer.add_page(banner_reader.pages[0])
    with open(output_pdf, "wb") as f:
        writer.write(f)

def remove_page_from_pdf(input_pdf: str, output_pdf: str, page_number: int):
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    if 0 <= page_number < len(reader.pages):
        for i, page in enumerate(reader.pages):
            if i != page_number:
                writer.add_page(page)
    with open(output_pdf, "wb") as f:
        writer.write(f)

def add_banner_to_epub(input_epub: str, output_epub: str, banner_image_path: str, position: str):
    book = epub.read_epub(input_epub)
    banner_item = epub.EpubImage()
    with open(banner_image_path, "rb") as f:
        banner_item.content = f.read()
    banner_item.file_name = "banner.jpg"
    banner_item.id = "banner"
    book.add_item(banner_item)
    banner_html = epub.EpubHtml(title="Banner", file_name="banner.xhtml")
    banner_html.content = f'<img src="banner.jpg" alt="Banner" style="width:100%;"/>'.encode()
    book.add_item(banner_html)
    if position in ["first", "both"]:
        book.spine.insert(0, banner_html)
        book.toc.insert(0, banner_html)
    if position in ["last", "both"]:
        book.spine.append(banner_html)
        book.toc.append(banner_html)
    epub.write_epub(output_epub, book)
