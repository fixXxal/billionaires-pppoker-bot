"""
Google Vision API + OCR.space integration for receipt/slip OCR
Extracts payment details from uploaded images
Uses Google Vision as primary, OCR.space as fallback
"""

import os
import re
import requests
import base64
import json
import tempfile
from google.cloud import vision
from google.oauth2 import service_account

# Load API keys from environment
OCR_API_KEY = os.getenv('OCR_API_KEY', 'K86220364088957')
OCR_API_URL = 'https://api.ocr.space/parse/image'

# Initialize Google Vision client (cached)
_vision_client = None


def get_vision_client():
    """
    Initialize and return Google Vision client
    Handles credentials from environment variable
    """
    global _vision_client

    if _vision_client is not None:
        return _vision_client

    try:
        # Check if credentials JSON is in environment variable
        credentials_json = os.getenv('GOOGLE_CREDENTIALS_JSON')

        if credentials_json:
            # Parse JSON from environment variable
            credentials_dict = json.loads(credentials_json)

            # Create credentials object
            credentials = service_account.Credentials.from_service_account_info(credentials_dict)

            # Initialize client with credentials
            _vision_client = vision.ImageAnnotatorClient(credentials=credentials)
            print("✅ Google Vision client initialized from environment variable")
            return _vision_client
        else:
            # Try default credentials (for local development with JSON file)
            _vision_client = vision.ImageAnnotatorClient()
            print("✅ Google Vision client initialized from default credentials")
            return _vision_client

    except Exception as e:
        print(f"⚠️ Failed to initialize Google Vision client: {e}")
        return None


def extract_text_with_google_vision(image_bytes):
    """
    Extract text from image using Google Cloud Vision API

    Args:
        image_bytes: Image content as bytes

    Returns:
        str: Extracted text from the image, or None if failed
    """
    try:
        client = get_vision_client()

        if client is None:
            return None

        # Create image object
        image = vision.Image(content=image_bytes)

        # Perform text detection
        response = client.text_detection(image=image)

        # Check for errors
        if response.error.message:
            raise Exception(f'Google Vision API Error: {response.error.message}')

        # Extract full text
        if response.text_annotations:
            # First annotation contains the full detected text
            full_text = response.text_annotations[0].description
            print(f"✅ Google Vision extracted {len(full_text)} characters")
            return full_text

        return ""

    except Exception as e:
        print(f"⚠️ Google Vision error: {e}")
        return None


def extract_text_with_ocr_space(image_bytes):
    """
    Extract text from image using OCR.space API (fallback)

    Args:
        image_bytes: Image content as bytes

    Returns:
        str: Extracted text from the image
    """
    try:
        # Encode image to base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')

        # Prepare payload for OCR.space API
        payload = {
            'apikey': OCR_API_KEY,
            'base64Image': f'data:image/jpeg;base64,{base64_image}',
            'language': 'eng',
            'isOverlayRequired': False,
            'detectOrientation': True,
            'scale': True,
            'OCREngine': 2,  # Engine 2 is more accurate
        }

        # Make API request
        response = requests.post(OCR_API_URL, data=payload, timeout=30)
        result = response.json()

        # Check for errors
        if result.get('IsErroredOnProcessing'):
            error_msg = result.get('ErrorMessage', ['Unknown error'])[0]
            raise Exception(f'OCR API Error: {error_msg}')

        # Extract text from response
        if result.get('ParsedResults'):
            parsed_text = result['ParsedResults'][0].get('ParsedText', '')
            print(f"✅ OCR.space extracted {len(parsed_text)} characters")
            return parsed_text

        return ""
    except Exception as e:
        print(f"⚠️ OCR.space error: {e}")
        return ""


def extract_text_from_image(image_bytes):
    """
    Extract text from image using Google Vision (primary) with OCR.space fallback

    Args:
        image_bytes: Image content as bytes

    Returns:
        str: Extracted text from the image
    """
    # Try Google Vision first (better accuracy)
    print("🔍 Attempting Google Vision OCR...")
    text = extract_text_with_google_vision(image_bytes)

    if text:
        print("✅ Using Google Vision result")
        return text

    # Fall back to OCR.space
    print("🔄 Falling back to OCR.space...")
    text = extract_text_with_ocr_space(image_bytes)

    if text:
        print("✅ Using OCR.space result")
        return text

    print("❌ Both OCR methods failed")
    return ""


def parse_payment_details(text):
    """
    Parse extracted text to identify payment details (optimized for MIB/BML receipts)

    Args:
        text: Extracted text from receipt/slip

    Returns:
        dict: Parsed payment details with keys:
            - reference_number: Transaction/reference number
            - sender_name: Name of sender
            - receiver_name: Name of receiver
            - amount: Transaction amount
            - bank: Bank name (BML, MIB, etc.)
            - currency: Currency (MVR, USD, etc.)
            - raw_text: Full extracted text for verification
    """
    details = {
        'reference_number': None,
        'sender_name': None,
        'receiver_name': None,
        'receiver_account_number': None,
        'amount': None,
        'bank': None,
        'currency': None,
        'raw_text': text
    }

    if not text:
        return details

    # Convert to uppercase for easier matching
    text_upper = text.upper()
    lines = [line.strip() for line in text.split('\n') if line.strip()]

    # --- Extract Bank Name ---
    if 'BANK OF MALDIVES' in text_upper:
        details['bank'] = 'BML'
    elif 'MALDIVES ISLAMIC BANK' in text_upper:
        details['bank'] = 'MIB'
    elif 'BML' in text_upper:
        details['bank'] = 'BML'
    elif 'MIB' in text_upper:
        details['bank'] = 'MIB'
    elif 'SBI' in text_upper or 'STATE BANK' in text_upper:
        details['bank'] = 'SBI'

    # --- Extract Amount and Currency ---
    # Patterns for Maldivian bank receipts
    amount_patterns = [
        r'MVR\s*([0-9,]+\.?\d{0,2})',  # MVR 65.00 or MVR 1,000.00
        r'([0-9,]+\.\d{2})\s*MVR',  # 100.00 MVR
        r'AMOUNT[\s:]+([0-9,]+\.?\d{0,2})',  # Amount: 1000.00
        r'(?:^|\n)([0-9]+\.\d{2})(?:\s*$|\n)',  # Standalone 100.00
    ]

    for pattern in amount_patterns:
        match = re.search(pattern, text_upper)
        if match:
            amount_str = match.group(1).replace(',', '').strip()
            try:
                amount_value = float(amount_str)
                # Only accept reasonable amounts (between 1 and 1 million)
                if 1.0 <= amount_value <= 1000000.0:
                    details['amount'] = amount_value
                    # Determine currency
                    if 'USD' in text_upper:
                        details['currency'] = 'USD'
                    else:
                        details['currency'] = 'MVR'  # Default for Maldivian banks
                    break
            except ValueError:
                continue

    # --- Extract Reference/Transaction Number ---
    # Enhanced patterns for MIB and BML receipts
    # BML: Can be alphanumeric (e.g., BLAZ133378629134)
    # MIB: Usually numeric (e.g., 759383063)
    ref_patterns = [
        r'REFERENCE[\s#:]+([A-Z0-9]+)',  # Reference BLAZ133378629134 or Reference 759383063
        r'REFERENCE\s*#?\s*\n\s*([A-Z0-9]{6,})',  # Reference #\n759435556 or BLAZ133
        r'REF[\s#:]+([A-Z0-9]+)',  # Ref: BLAZ133378629134
        r'TRANSACTION\s+(?:ID|NUMBER|NO)[\s:]+([A-Z0-9]+)',  # Transaction ID: XXX
        r'REFERENCE\s*#\s*\n\s*([A-Z0-9]{6,})',  # Reference #\n[any alphanumeric]
        r'REFERENCE\s*#?\s*[\n\s]*([A-Z0-9]{6,})',  # Flexible reference pattern
    ]

    for pattern in ref_patterns:
        match = re.search(pattern, text_upper, re.MULTILINE)
        if match:
            ref = match.group(1).strip()
            # Accept references with 6+ characters (can be numeric or alphanumeric)
            if len(ref) >= 6 and len(ref) <= 30:  # Max 30 chars to avoid capturing junk
                details['reference_number'] = ref
                break

    # If no reference found with labeled patterns, look for standalone strings
    if not details['reference_number']:
        # Check if we see "Reference #" or "Reference" followed by a number on next lines
        ref_index = -1
        for i, line in enumerate(lines):
            if re.search(r'REFERENCE\s*#?', line.upper()):
                ref_index = i
                break

        # Look for reference number in the next few lines after "Reference #"
        if ref_index >= 0:
            for i in range(ref_index + 1, min(ref_index + 5, len(lines))):
                line_upper = lines[i].upper().strip()
                # Accept any alphanumeric string 6-30 chars (covers both MIB numeric and BML alphanumeric)
                if re.match(r'^[A-Z0-9]{6,30}$', line_upper):
                    # If we're right after "Reference" label, accept even long numeric strings
                    # Otherwise skip if it looks like an account number (all digits and 16+ chars)
                    if not (line_upper.isdigit() and len(line_upper) >= 16):
                        details['reference_number'] = line_upper
                        break

        # If still not found, look for standalone alphanumeric strings anywhere
        if not details['reference_number']:
            for line in lines:
                line_upper = line.upper().strip()
                # Look for alphanumeric strings 8-30 chars
                if re.match(r'^[A-Z0-9]{8,30}$', line_upper):
                    # Skip if it looks like an account number (all digits and 16+ chars)
                    # This allows 8-15 digit pure numeric references to be captured
                    if not (line_upper.isdigit() and len(line_upper) >= 16):
                        details['reference_number'] = line_upper
                        break

    # --- Extract Names ---
    # Skip words that are not names (labels, bank names, etc.)
    skip_name_words = ['BANK', 'BML', 'MIB', 'CREATED DATE', 'STATUS DATE', 'PURPOSE',
                       'REFERENCE', 'AMOUNT', 'STATUS', 'MESSAGE', 'FROM', 'TO',
                       'MALDIVES ISLAMIC BANK', 'BANK OF MALDIVES', 'TRANSACTION DATE',
                       'THANK YOU', 'YOUR REQUEST', 'HAS BEEN', 'SUBMITTED', 'PROCESSING',
                       'REMARKS', 'SUCCESS', 'TRANSACTION', 'MVR', 'USD', 'USDT']

    # Helper function to check if a string looks like an amount (e.g., "MVR 100.00" or "100.00")
    def looks_like_amount(text):
        """Check if text appears to be a currency amount"""
        text_check = text.upper().strip()
        # Check for currency keywords
        if any(curr in text_check for curr in ['MVR', 'USD', 'USDT', 'RF', 'RUFIYAA']):
            return True
        # Check if it's just a number with decimal (like "100.00" or "1,234.56")
        if re.match(r'^[0-9,]+\.\d{2}$', text_check):
            return True
        # Check if it starts with a number
        if re.match(r'^\d', text_check):
            return True
        return False

    # Pattern 1: "From" field - Enhanced for BML format
    from_patterns = [
        r'FROM[\s:]+([A-Z][A-Z0-9\s\.]+?)(?:\n|$)',  # From AHMD.FIXAL (BML format - name on same line)
        r'FROM\s*\n\s*([A-Z][A-Z0-9\s\.]+?)(?:\n|\s{2,})',  # From\n  AHMD.FIXAL (MIB format - name on next line)
    ]

    for pattern in from_patterns:
        match = re.search(pattern, text_upper, re.MULTILINE)
        if match:
            name = match.group(1).strip()
            # Clean up the name
            name = re.sub(r'\s+', ' ', name)
            # Remove trailing account numbers if any
            name = re.sub(r'\s*\d{10,}$', '', name)

            # Skip if it looks like an amount
            if looks_like_amount(name):
                continue

            # Validate it looks like a name (letters/dots/numbers, not pure text labels)
            # BML names often have dots like AHMD.FIXAL
            if (len(name) >= 3 and
                re.search(r'[A-Z]', name) and
                not any(skip_word in name.upper() for skip_word in skip_name_words)):
                # Preserve format (keep dots, capitalize properly)
                details['sender_name'] = name.title().replace('.', '.')
                break

    # Track where sender was found (for MIB receipts where values appear after labels)
    sender_line_index = -1

    # If no sender found with patterns, look for name after "From" label
    if not details['sender_name']:
        from_index = -1
        for i, line in enumerate(lines):
            if line.upper().strip() == 'FROM':
                from_index = i
                break

        # Look for name in the next few lines after "From" (MIB has labels separate from values)
        if from_index >= 0:
            # Check next 10 lines for a name-like string
            for offset in range(1, min(11, len(lines) - from_index)):
                potential_name = lines[from_index + offset].strip()
                potential_name_upper = potential_name.upper()

                # Skip if it looks like an amount
                if looks_like_amount(potential_name):
                    continue

                # Check if it looks like a name (has letters, spaces/dots, not pure digits, not too long)
                if (len(potential_name) >= 3 and
                    re.search(r'[A-Za-z]', potential_name) and
                    not potential_name.isdigit() and
                    len(potential_name) < 50 and
                    not re.match(r'^\d{10,}$', potential_name)):  # Not an account number

                    # Skip if it contains any skip words or looks like UI text
                    if (not any(skip_word in potential_name_upper for skip_word in skip_name_words) and
                        not re.search(r'(THANK|YOUR|REQUEST|SUBMITTED|PROCESSING|MESSAGE|REMARKS)', potential_name_upper)):

                        # Only accept if it looks like a proper name (dots or short words, not long sentences)
                        # Names are usually: AHMD.FIXAL, MOHAMED ALI, etc. (not "Thank you. Your request...")
                        if '.' in potential_name or len(potential_name.split()) <= 3:
                            # Remove any trailing numbers (account numbers)
                            potential_name = re.sub(r'\s*\d{10,}$', '', potential_name)
                            if len(potential_name) >= 3:
                                details['sender_name'] = potential_name.title()
                                sender_line_index = from_index + offset  # Track where we found it
                                break

    # Pattern 2: "To" field (receiver) - Enhanced for BML format
    to_patterns = [
        r'TO[\s:]+([A-Z][A-Z0-9\s\.]+?)(?:\s*\d{10,}|\n|$)',  # To AHMD.FIXAL 90103101325241000 (BML - name+account on same line)
        r'TO\s*\n\s*([A-Z][A-Z0-9\s\.]+?)(?:\n|\s{2,})',  # To\n  AHMD.FIXAL (MIB format)
    ]

    for pattern in to_patterns:
        match = re.search(pattern, text_upper, re.MULTILINE)
        if match:
            name = match.group(1).strip()
            # Clean up the name
            name = re.sub(r'\s+', ' ', name)
            # Remove trailing account numbers if any (BML has them on same line)
            name = re.sub(r'\s*\d{10,}$', '', name).strip()

            # Skip if it looks like an amount
            if looks_like_amount(name):
                continue

            # Skip if it matches the sender name (avoid picking up sender as receiver)
            if details['sender_name'] and name.upper() == details['sender_name'].upper():
                continue

            # Validate it looks like a name (not a label)
            if (len(name) >= 3 and
                re.search(r'[A-Z]', name) and
                not any(skip_word in name.upper() for skip_word in skip_name_words)):
                # Preserve format (keep dots, capitalize properly)
                details['receiver_name'] = name.title().replace('.', '.')
                break

    # If no receiver found with patterns, look for name after "To" label
    if not details['receiver_name']:
        to_index = -1
        for i, line in enumerate(lines):
            if line.upper().strip() == 'TO':
                to_index = i
                break

        # Look for name in the next few lines after "To" (MIB has labels separate from values)
        if to_index >= 0:
            # Check next 15 lines for a name-like string (need to look further for MIB)
            for offset in range(1, min(16, len(lines) - to_index)):
                current_index = to_index + offset
                potential_name = lines[current_index].strip()

                # Skip if this is before or at the sender position (for MIB where sender/receiver are sequential)
                if sender_line_index >= 0 and current_index <= sender_line_index:
                    continue

                # Skip if this matches the sender name exactly (avoid duplicate when sender name appears after "To")
                if details['sender_name'] and potential_name.upper() == details['sender_name'].upper():
                    continue

                # Skip if it looks like an amount
                if looks_like_amount(potential_name):
                    continue

                # Check if it looks like a name (has letters, spaces/dots, not pure digits, not too long)
                if (len(potential_name) >= 3 and
                    re.search(r'[A-Za-z]', potential_name) and
                    not potential_name.isdigit() and
                    len(potential_name) < 50 and
                    not re.match(r'^\d{10,}$', potential_name)):  # Not an account number

                    potential_name_upper = potential_name.upper()

                    # Skip if it contains any skip words or looks like UI text
                    if (not any(skip_word in potential_name_upper for skip_word in skip_name_words) and
                        not re.search(r'(THANK|YOUR|REQUEST|SUBMITTED|PROCESSING|MESSAGE|REMARKS|BEEN)', potential_name_upper)):

                        # Only accept if it looks like a proper name (dots or short words, not long sentences)
                        if '.' in potential_name or len(potential_name.split()) <= 3:
                            # Remove any trailing numbers (account numbers)
                            clean_name = re.sub(r'\s*\d{10,}$', '', potential_name)
                            if len(clean_name) >= 3:
                                details['receiver_name'] = clean_name.title()
                                break

    # --- Extract Receiver Account Number ---
    # Look for account numbers near "To" label
    # BML: 13 digits (e.g., 7730000646797), MIB: 17 digits (e.g., 90103101325241000)
    if not details['receiver_account_number']:
        to_index = -1
        for i, line in enumerate(lines):
            if line.upper().strip() == 'TO':
                to_index = i
                break

        if to_index >= 0:
            # Check next few lines after "To" for account number
            for offset in range(1, min(10, len(lines) - to_index)):
                potential_line = lines[to_index + offset].strip()

                # Try to find account number in the line (may be standalone or mixed with name)
                # Look for 10-20 digit sequences
                account_match = re.search(r'\b(\d{10,20})\b', potential_line)
                if account_match:
                    potential_account = account_match.group(1)

                    # Make sure it's not the reference number we already extracted
                    if details['reference_number'] and potential_account == details['reference_number']:
                        continue

                    # This is likely the receiver account number
                    details['receiver_account_number'] = potential_account
                    break

    return details


def format_extracted_details(details, show_raw=False):
    """
    Format extracted details into a readable message

    Args:
        details: Dictionary of parsed payment details
        show_raw: If True, include raw extracted text for debugging

    Returns:
        str: Formatted message for display
    """
    message = "✅ *Payment Slip Detected*\n\n"

    if details['amount']:
        currency = details['currency'] or ''
        message += f"💰 *Amount:* {currency} {details['amount']:,.2f}\n"

    if details['reference_number']:
        message += f"📋 *Reference:* `{details['reference_number']}`\n"

    if details['bank']:
        message += f"🏦 *Bank:* {details['bank']}\n"

    if details['sender_name']:
        message += f"👤 *Sender:* {details['sender_name']}\n"

    # Check if any details were extracted
    has_key_details = any([details['amount'], details['reference_number'], details['bank'], details['sender_name']])

    if has_key_details:
        message += "\n⏳ *Status:* Processing\n"
        message += "_You'll receive an update once verification is complete._"
    else:
        message += "⚠️ _Some details may be inaccurate._\n"
        message += "_Verification is in progress._\n"

    # Show raw extracted text for debugging (admin only)
    if show_raw and details['raw_text']:
        message += f"\n\n🔍 *Raw Text (Debug):*\n```\n{details['raw_text'][:500]}...\n```"

    return message


async def process_receipt_image(file_bytes):
    """
    Complete pipeline: Extract text and parse payment details from receipt image

    Args:
        file_bytes: Image file content as bytes

    Returns:
        dict: Parsed payment details
    """
    # Extract text using Vision API
    extracted_text = extract_text_from_image(file_bytes)

    # Parse the text for payment details
    details = parse_payment_details(extracted_text)

    return details
