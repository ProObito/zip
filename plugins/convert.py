import os
import zipfile
from pyrogram import Client, filters
from ebooklib import epub
from PyPDF2 import PdfReader, PdfWriter
from helper.database import db, get_thumbnail
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_message(filters.command("convert"))
async def convert_menu(bot, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📘 To PDF", callback_data="to_pdf"),
         InlineKeyboardButton("📦 To ZIP", callback_data="to_zip")],
        [InlineKeyboardButton("📚 To EPUB", callback_data="to_epub"),
         InlineKeyboardButton("🖼️ To CBZ", callback_data="to_cbz")]
    ])
    await message.reply_text(
        "📂 Choose the format to convert your file:",
        reply_markup=keyboard
    )

@Client.on_callback_query(filters.regex("^to_"))
async def convert_callback(bot, query):
    user_id = query.from_user.id
    format_to = query.data.replace("to_", "")
    await query.message.edit_text(f"📤 Send the file you want to convert to **{format_to.upper()}**")

    # Wait for file
    response = await bot.listen(user_id, filters.document)
    file_path = await response.download()
    base, ext = os.path.splitext(file_path)

    output_file = None
    try:
        if format_to == "pdf":
            if ext.lower() == ".epub":
                output_file = base + ".pdf"
                book = epub.read_epub(file_path)
                writer = PdfWriter()
                for item in book.get_items():
                    if item.get_type() == epub.ITEM_DOCUMENT:
                        writer.add_blank_page()  # Placeholder page
                with open(output_file, "wb") as f:
                    writer.write(f)

            elif ext.lower() in [".zip", ".cbz"]:
                output_file = base + ".pdf"
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    pdf_writer = PdfWriter()
                    for item in zip_ref.namelist():
                        if item.lower().endswith(".jpg") or item.lower().endswith(".png"):
                            pdf_writer.add_blank_page()
                    with open(output_file, "wb") as f:
                        pdf_writer.write(f)

        elif format_to == "zip":
            output_file = base + ".zip"
            with zipfile.ZipFile(output_file, "w") as zipf:
                zipf.write(file_path, os.path.basename(file_path))

        elif format_to == "epub":
            output_file = base + ".epub"
            book = epub.EpubBook()
            book.set_identifier("id123456")
            book.set_title("Converted File")
            book.set_language("en")
            c1 = epub.EpubHtml(title='Content', file_name='chap_01.xhtml', lang='en')
            c1.content = f"<h1>Converted from {ext}</h1>"
            book.add_item(c1)
            epub.write_epub(output_file, book, {})

        elif format_to == "cbz":
            output_file = base + ".cbz"
            with zipfile.ZipFile(output_file, "w") as zipf:
                zipf.write(file_path, os.path.basename(file_path))

        else:
            await query.message.reply_text("❌ Unsupported conversion type.")
            return

        thumb = await db.get_thumbnail(user_id)
        thumb_path = get_thumbnail(user_id) if thumb else None

        await bot.send_document(
            chat_id=user_id,
            document=output_file,
            thumb=thumb_path if thumb_path else None,
            caption=f"✅ Converted to {format_to.upper()}"
        )
    except Exception as e:
        await query.message.reply_text(f"❌ Conversion failed: `{e}`")
    finally:
        try:
            os.remove(file_path)
            if output_file and os.path.exists(output_file):
                os.remove(output_file)
        except:
            pass


# 📄 Remove or Add Page Command
@Client.on_message(filters.command(["addpage", "removepage"]))
async def pdf_page_edit(bot, message):
    cmd = message.command[0]
    user_id = message.from_user.id

    await message.reply_text("📥 Send the PDF file first:")
    response = await bot.listen(user_id, filters.document)
    pdf_path = await response.download()
    reader = PdfReader(pdf_path)
    writer = PdfWriter()

    if cmd == "removepage":
        await message.reply_text("❌ Send the page number you want to remove:")
        page_msg = await bot.listen(user_id, filters.text)
        remove_page = int(page_msg.text) - 1

        for i in range(len(reader.pages)):
            if i != remove_page:
                writer.add_page(reader.pages[i])

    elif cmd == "addpage":
        await message.reply_text("📄 Send another PDF to insert:")
        page_pdf = await bot.listen(user_id, filters.document)
        add_path = await page_pdf.download()
        add_reader = PdfReader(add_path)

        await message.reply_text("📍 Send page number to insert after:")
        pos_msg = await bot.listen(user_id, filters.text)
        position = int(pos_msg.text)

        for i in range(len(reader.pages)):
            writer.add_page(reader.pages[i])
            if i + 1 == position:
                for p in add_reader.pages:
                    writer.add_page(p)

    output_path = "downloads/edited.pdf"
    with open(output_path, "wb") as f:
        writer.write(f)

    thumb = await db.get_thumbnail(user_id)
    thumb_path = get_thumbnail(user_id) if thumb else None

    await bot.send_document(
        chat_id=user_id,
        document=output_path,
        thumb=thumb_path if thumb_path else None,
        caption="✅ Page operation complete."
    )

    os.remove(pdf_path)
    if os.path.exists(output_path):
        os.remove(output_path)
