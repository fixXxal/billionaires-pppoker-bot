"""
Test Vision API with sample receipts
"""
import asyncio
from vision_api import process_receipt_image, format_extracted_details

async def test_receipts():
    import os

    # Detect if running on Windows or Linux
    if os.name == 'nt':  # Windows
        base_path = 'C:\\billionaires\\slipss\\'
    else:  # Linux/WSL
        base_path = '/mnt/c/billionaires/slipss/'

    # Test MIB receipt
    print("=" * 60)
    print("Testing MIB Receipt")
    print("=" * 60)
    with open(base_path + 'photo_2025-11-07_23-30-08.jpg', 'rb') as f:
        mib_bytes = f.read()

    mib_details = await process_receipt_image(mib_bytes)
    print(format_extracted_details(mib_details, show_raw=True))

    print("\n" + "=" * 60)
    print("Testing BML Receipt")
    print("=" * 60)
    # Test BML receipt
    with open(base_path + 'photo_2025-11-08_01-42-56.jpg', 'rb') as f:
        bml_bytes = f.read()

    bml_details = await process_receipt_image(bml_bytes)
    print(format_extracted_details(bml_details, show_raw=True))

if __name__ == '__main__':
    asyncio.run(test_receipts())
