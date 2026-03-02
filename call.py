#!/usr/bin/env python3
"""
AVR Outbound Call Tool
Usage: python call.py <phone_number>

Examples:
  python call.py 068155658      # Local Moldova format
  python call.py 37368155658    # International format (will be converted)
"""

import urllib.request
import json
import sys

AMI_URL = "http://localhost:6006/originate"
DEFAULT_CONTEXT = "demo"
DEFAULT_EXTEN = "5001"
DEFAULT_CALLERID = "22011180"

def make_call(phone_number: str):
    """Initiate an outbound call via avr-ami API"""
    # Build channel - IPHost expects local format 0XXXXXXXXX
    # The dialplan handles format conversion
    channel = f"PJSIP/{phone_number}@iphost-endpoint"

    payload = {
        "channel": channel,
        "exten": DEFAULT_EXTEN,
        "context": DEFAULT_CONTEXT,
        "priority": 1,
        "callerid": DEFAULT_CALLERID
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        AMI_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode())
        print(f"✓ Call initiated: {result}")
        return result
    except urllib.error.HTTPError as e:
        print(f"✗ Error: {e.code} - {e.read().decode()}")
        return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    phone = sys.argv[1]
    print(f"Calling {phone}...")
    make_call(phone)
