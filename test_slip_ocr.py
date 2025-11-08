"""
Test OCR on the specific slip image
"""
import asyncio
import vision_api

async def test_ocr():
    """Test OCR on the slip"""
    # Read the image file
    with open('/mnt/c/billionaires/slipss/photo_2025-11-08_11-51-09.jpg', 'rb') as f:
        file_bytes = f.read()

    print(f"📸 Image size: {len(file_bytes)} bytes\n")

    print("🔍 Processing with OCR...\n")
    extracted_details = await vision_api.process_receipt_image(file_bytes)

    print("=" * 60)
    print("📄 EXTRACTED RECEIPT DETAILS:")
    print("=" * 60)

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

    print("\n" + "=" * 60)
    print("📝 RAW EXTRACTED TEXT:")
    print("=" * 60)
    if extracted_details['raw_text']:
        print(extracted_details['raw_text'])
    else:
        print("(No text extracted)")

    print("\n" + "=" * 60)

if __name__ == '__main__':
    asyncio.run(test_ocr())
