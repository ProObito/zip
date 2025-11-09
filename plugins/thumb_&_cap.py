from pyrogram import Client, filters
from pyrogram.types import Message
import os
from PyPDF2 import PdfReader, PdfWriter

# === Helper Function ===
def compress_pdf(input_path, output_path):
    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page in reader.pages:
        page.compress_content_streams()  # reduce PDF size
        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)

# === Command Handler ===
@Bot.on_message(filters.command("compdf") & filters.private)
async def compdf_cmd(client: Client, message: Message):
    await message.reply_text("📄 Send me the PDF you want to compress.")

# === PDF File Handler ===
@Bot.on_message(filters.document & filters.private)
async def handle_pdf(client: Client, message: Message):
    if message.document.mime_type != "application/pdf":
        return await message.reply_text("❌ Please send a valid PDF file.")

    file_id = message.document.file_id
    file_name = message.document.file_name or "input.pdf"

    input_pdf = f"downloads/{file_name}"
    output_pdf = f"downloads/compressed_{file_name}"

    # Download PDF
    m = await message.reply_text("⬇️ Downloading your PDF...")
    await client.download_media(message, file_name=input_pdf)

    await m.edit("⚙️ Compressing your PDF...")

    try:
        compress_pdf(input_pdf, output_pdf)
        await message.reply_document(
            document=output_pdf,
            caption="✅ PDF successfully compressed!"
        )
    except Exception as e:
        await message.reply_text(f"❌ Error while compressing PDF:\n`{e}`")
    finally:
        # Clean up
        if os.path.exists(input_pdf):
            os.remove(input_pdf)
        if os.path.exists(output_pdf):
            os.remove(output_pdf)
