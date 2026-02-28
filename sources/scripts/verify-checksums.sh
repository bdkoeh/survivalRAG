#!/usr/bin/env bash
# verify-checksums.sh - Verify SHA-256 checksums of all downloaded PDFs
#
# Reads sources/checksums.sha256 and verifies each file.
# Reports pass/fail per file and overall status.
# Exits non-zero if any file fails verification.
#
# Usage: bash sources/scripts/verify-checksums.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CHECKSUMS_FILE="$SOURCES_DIR/checksums.sha256"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ ! -f "$CHECKSUMS_FILE" ]; then
    echo -e "${RED}ERROR${NC}: Checksums file not found: $CHECKSUMS_FILE"
    echo "Run download-all.sh first to generate checksums."
    exit 1
fi

echo "============================================"
echo "SurvivalRAG Checksum Verification"
echo "============================================"
echo ""
echo "Checksums file: $CHECKSUMS_FILE"
echo ""

PASS=0
FAIL=0
MISSING=0
TOTAL=0

while IFS= read -r line; do
    # Skip empty lines and comments
    [ -z "$line" ] && continue
    [[ "$line" =~ ^# ]] && continue

    TOTAL=$((TOTAL + 1))

    # Parse checksum and relative path
    expected_hash=$(echo "$line" | awk '{print $1}')
    rel_path=$(echo "$line" | awk '{print $2}')
    full_path="$SOURCES_DIR/$rel_path"

    if [ ! -f "$full_path" ]; then
        echo -e "${RED}MISSING${NC}: $rel_path"
        MISSING=$((MISSING + 1))
        continue
    fi

    actual_hash=$(sha256sum "$full_path" | cut -d' ' -f1)

    if [ "$actual_hash" = "$expected_hash" ]; then
        echo -e "${GREEN}PASS${NC}: $rel_path"
        PASS=$((PASS + 1))
    else
        echo -e "${RED}FAIL${NC}: $rel_path"
        echo "  Expected: $expected_hash"
        echo "  Actual:   $actual_hash"
        FAIL=$((FAIL + 1))
    fi
done < "$CHECKSUMS_FILE"

echo ""
echo "============================================"
echo "Results: $PASS passed, $FAIL failed, $MISSING missing (of $TOTAL)"
echo "============================================"

if [ "$FAIL" -gt 0 ] || [ "$MISSING" -gt 0 ]; then
    echo -e "${RED}VERIFICATION FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}ALL CHECKSUMS VERIFIED${NC}"
    exit 0
fi
