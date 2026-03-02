#!/bin/bash
# AVR Outbound Call Tool
# Usage: ./call.sh <phone_number>
#
# Examples:
#   ./call.sh 068155658      # Local Moldova format
#   ./call.sh 37368155658    # International format (will be converted)

if [ -z "$1" ]; then
    echo "Usage: $0 <phone_number>"
    echo "Example: $0 068155658"
    exit 1
fi

PHONE="$1"
echo "Calling $PHONE..."

curl -s -X POST http://localhost:6006/originate \
    -H "Content-Type: application/json" \
    -d "{\"channel\": \"PJSIP/${PHONE}@iphost-endpoint\", \"exten\": \"5001\", \"context\": \"demo\", \"priority\": 1, \"callerid\": \"22011180\"}"
echo
