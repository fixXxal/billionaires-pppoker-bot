"""
Manual OCR test for a specific deposit photo
"""
import asyncio
import os
from telegram import Bot
from dotenv import load_dotenv
import vision_api

load_dotenv()

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
PHOTO_FILE_ID = "AgACAgUAAxkBAAIBcmkOOpwT-VGFnwOEub2nhrBXhQpCAAIwC2sbWwp4VGZszm13R_T5AQADAgAD"

async def test_ocr():
    """Download and process the deposit photo"""
    bot = Bot(token=TOKEN)

    print("🔍 Downloading photo...")
    file = await bot.get_file(PHOTO_FILE_ID)
    file_bytes = await file.download_as_bytearray()
    print(f"✅ Downloaded {len(file_bytes)} bytes")

    print("\n🔍 Processing with OCR...")
    extracted_details = await vision_api.process_receipt_image(bytes(file_bytes))

    print("\n" + "="*60)
    print("📄 EXTRACTED RECEIPT DETAILS:")
    print("="*60)

    if extracted_details['reference_number']:
        print(f"🔢 Reference Number: {extracted_details['reference_number']}")
    else:
        print("🔢 Reference Number: NOT FOUND")

    if extracted_details['amount']:
        curr = extracted_details['currency'] or ''
        print(f"💰 Amount: {curr} {extracted_details['amount']:,.2f}")
    else:
        print("💰 Amount: NOT FOUND")

    if extracted_details['bank']:
        print(f"🏦 Bank: {extracted_details['bank']}")
    else:
        print("🏦 Bank: NOT FOUND")

    if extracted_details['sender_name']:
        print(f"👤 Sender: {extracted_details['sender_name']}")
    else:
        print("👤 Sender: NOT FOUND")

    if extracted_details['receiver_name']:
        print(f"👤 Receiver: {extracted_details['receiver_name']}")
    else:
        print("👤 Receiver: NOT FOUND")

    print("\n" + "="*60)
    print("📝 RAW EXTRACTED TEXT:")
    print("="*60)
    if extracted_details['raw_text']:
        print(extracted_details['raw_text'])
    else:
        print("(No text extracted)")

    print("\n" + "="*60)

if __name__ == '__main__':
    asyncio.run(test_ocr())
