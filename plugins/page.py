from pyrogram import Client, filters
import fitz, os

print("✅ page.py loaded")

@Client.on_message(filters.command("getpage"))
async def get_page(_, m):
    if not m.reply_to_message or not m.reply_to_message.document:
        return await m.reply("⚠️ Reply to a PDF file with `/getpage <page_no>`")
    if len(m.command) < 2:
        return await m.reply("⚠️ Example: `/getpage 3`")
    page_no = int(m.command[1]) - 1
    file = await m.reply_to_message.download()
    try:
        pdf = fitz.open(file)
        if page_no < 0 or page_no >= len(pdf):
            return await m.reply("⚠️ Invalid page number.")
        pix = pdf[page_no].get_pixmap(dpi=150)
        img_path = f"downloads/{m.from_user.id}_page{page_no+1}.png"
        pix.save(img_path)
        await m.reply_photo(img_path, caption=f"📄 Page {page_no+1}")
    except Exception as e:
        await m.reply(f"❌ Error: {e}")
    finally:
        os.remove(file)
        if os.path.exists(img_path): os.remove(img_path)

@Client.on_message(filters.command("addpage"))
async def add_page(_, m):
    if len(m.command) < 2 or not m.reply_to_message or not m.reply_to_message.document:
        return await m.reply("⚠️ Reply to a PDF with `/addpage <image>` attached as photo.")
    if not m.reply_to_message.photo:
        return await m.reply("⚠️ You must reply to an image to add.")
    pdf_file = await m.reply_to_message.download()
    image_file = await m.reply_to_message.download()
    try:
        pdf = fitz.open(pdf_file)
        img_doc = fitz.open(image_file)
        pdf.insert_pdf(img_doc)
        output = f"downloads/{m.from_user.id}_added.pdf"
        pdf.save(output)
        await m.reply_document(output, caption="✅ Page added successfully.")
    except Exception as e:
        await m.reply(f"❌ Error: {e}")
    finally:
        for f in [pdf_file, image_file, output]:
            if os.path.exists(f): os.remove(f)
