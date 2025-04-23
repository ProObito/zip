import re
import zipfile
import tempfile
import asyncio
import shutil
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message
import os, re, zipfile, tempfile, asyncio

def natural_sort(files):
    return sorted(files, key=lambda f: [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', f)])

def remove_duplicates(file_list):
    """Keep base image (e.g., 1.jpg) and remove variants like 1t.jpg."""
    base_map = {}
    valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".img")

    for file in file_list:
        name, ext = os.path.splitext(os.path.basename(file))
        if ext.lower() not in valid_extensions:
            continue
        match = re.match(r"^(\d+)[a-zA-Z]?$", name)
        if match:
            base = match.group(1)
            if base not in base_map or not name.endswith("t"):  # Prefer base over variant
                base_map[base] = file
    return list(base_map.values())

def generate_pdf(image_files, output_path):
    image_iter = (Image.open(f).convert("RGB") for f in image_files)
    first = next(image_iter)
    first.save(output_path, save_all=True, append_images=image_iter)

def natural_sort(file_list):
    """Sorts file names naturally (e.g., img1, img2, img10 instead of img1, img10, img2)."""
    return sorted(file_list, key=lambda f: [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', f)])

@Client.on_message(filters.command("pdf") & filters.private & filters.user(ADMINS))
async def pdf_handler(bot: Client, message: Message):
    await message.reply_text("📂 Please send a ZIP file containing images. You have 30 seconds.")

    try:
        zip_msg = await bot.listen(
            message.chat.id, 
            filters.document & filters.create(lambda _, __, m: m.document and m.document.file_name.endswith(".zip")),
            timeout=30
        )
    except asyncio.TimeoutError:
        return await message.reply_text("⏰ Timeout: No ZIP file received within 30 seconds.")

    zip_name = os.path.splitext(zip_msg.document.file_name)[0]

    # Use temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = os.path.join(temp_dir, zip_msg.document.file_name)
        extract_folder = os.path.join(temp_dir, f"{zip_name}_extracted")
        pdf_path = os.path.join(temp_dir, f"{zip_name}.pdf")

        # Download ZIP file
        await zip_msg.download(zip_path)

        # Extract ZIP file
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
        except zipfile.BadZipFile:
            return await message.reply_text("❌ Invalid ZIP file.")

        # Supported image formats
        valid_extensions = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff", ".img")

        # Get image files, sorted naturally
        image_files = natural_sort([
            os.path.join(extract_folder, f) for f in os.listdir(extract_folder)
            if f.lower().endswith(valid_extensions)
        ])

        if not image_files:
            return await message.reply_text("❌ No images found in the ZIP.")

        # Convert images to PDF without compression
        try:
            first_image = Image.open(image_files[0]).convert("RGB")

            # Open images without compression
            image_list = [Image.open(img).convert("RGB") for img in image_files[1:]]

            first_image.save(pdf_path, save_all=True, append_images=image_list)
        except Exception as e:
            return await message.reply_text(f"❌ Error converting to PDF: {e}")

        # Upload PDF with delay to avoid Telegram API rate limits
        await asyncio.sleep(2)  # Small delay
        await message.reply_document(pdf_path, caption=f"Here is your PDF: {zip_name}.pdf 📄")
