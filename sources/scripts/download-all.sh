#!/usr/bin/env bash
# download-all.sh - Download all Tier 1 source documents for SurvivalRAG
#
# Idempotent: skips files that already exist.
# Uses curl with retry logic and fallback URLs.
# Generates SHA-256 checksums after all downloads complete.
#
# Usage: bash sources/scripts/download-all.sh
#
# Expected output directory: sources/originals/{military,fema,cdc}/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ORIGINALS_DIR="$SOURCES_DIR/originals"
CHECKSUMS_FILE="$SOURCES_DIR/checksums.sha256"
REPORT_FILE="$SOURCES_DIR/scripts/download-report.txt"

# Counters
DOWNLOADED=0
SKIPPED=0
ERRORS=0
TOTAL=0

# Color output (if terminal supports it)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Initialize download report
echo "Download Report - $(date -u +"%Y-%m-%dT%H:%M:%SZ")" > "$REPORT_FILE"
echo "========================================" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

log_report() {
    echo "$1" >> "$REPORT_FILE"
}

# Download a file with primary URL and optional fallback
# Usage: download_file <dest_path> <primary_url> [fallback_url]
download_file() {
    local dest="$1"
    local primary_url="$2"
    local fallback_url="${3:-}"
    local filename
    filename="$(basename "$dest")"

    TOTAL=$((TOTAL + 1))

    # Skip if file already exists and is > 1KB (reject HTML error pages)
    if [ -f "$dest" ]; then
        local filesize
        filesize=$(wc -c < "$dest" | tr -d ' ')
        if [ "$filesize" -gt 1024 ]; then
            echo -e "${YELLOW}SKIP${NC} (exists, ${filesize} bytes): $filename"
            log_report "SKIP: $filename (exists, ${filesize} bytes)"
            SKIPPED=$((SKIPPED + 1))
            return 0
        else
            echo -e "${YELLOW}REDOWNLOAD${NC} (too small, likely error page): $filename"
            rm -f "$dest"
        fi
    fi

    # Create destination directory if needed
    mkdir -p "$(dirname "$dest")"

    # Try primary URL
    echo -e "DOWNLOADING: $filename"
    echo -e "  URL: $primary_url"
    if curl --retry 3 --retry-delay 5 -fSL --connect-timeout 30 --max-time 600 -o "$dest" "$primary_url" 2>/dev/null; then
        local filesize
        filesize=$(wc -c < "$dest" | tr -d ' ')
        if [ "$filesize" -gt 1024 ] && head -c 5 "$dest" | grep -q "%PDF"; then
            echo -e "  ${GREEN}OK${NC}: $filename (${filesize} bytes)"
            log_report "OK: $filename (${filesize} bytes) from primary URL"
            DOWNLOADED=$((DOWNLOADED + 1))
            return 0
        else
            echo -e "  ${YELLOW}WARNING${NC}: File invalid (${filesize} bytes, may not be PDF)"
            rm -f "$dest"
        fi
    else
        echo -e "  ${YELLOW}FAILED${NC}: Primary URL failed"
    fi

    # Try fallback URL if provided
    if [ -n "$fallback_url" ]; then
        echo -e "  Trying fallback: $fallback_url"
        if curl --retry 3 --retry-delay 5 -fSL --connect-timeout 30 --max-time 600 -o "$dest" "$fallback_url" 2>/dev/null; then
            local filesize
            filesize=$(wc -c < "$dest" | tr -d ' ')
            if [ "$filesize" -gt 1024 ] && head -c 5 "$dest" | grep -q "%PDF"; then
                echo -e "  ${GREEN}OK${NC}: $filename (${filesize} bytes) [fallback]"
                log_report "OK: $filename (${filesize} bytes) from fallback URL"
                DOWNLOADED=$((DOWNLOADED + 1))
                return 0
            else
                echo -e "  ${YELLOW}WARNING${NC}: Fallback file invalid (${filesize} bytes, may not be PDF)"
                rm -f "$dest"
            fi
        else
            echo -e "  ${YELLOW}FAILED${NC}: Fallback URL failed"
        fi
    fi

    # Try Wayback Machine as last resort (use id_ modifier for raw file, not HTML wrapper)
    local wayback_url="https://web.archive.org/web/2024id_/${primary_url}"
    echo -e "  Trying Wayback Machine: $wayback_url"
    if curl --retry 2 --retry-delay 5 -fSL --connect-timeout 30 --max-time 600 -o "$dest" "$wayback_url" 2>/dev/null; then
        local filesize
        filesize=$(wc -c < "$dest" | tr -d ' ')
        # Verify it is actually a PDF (not HTML wrapper)
        if [ "$filesize" -gt 1024 ] && head -c 5 "$dest" | grep -q "%PDF"; then
            echo -e "  ${GREEN}OK${NC}: $filename (${filesize} bytes) [wayback]"
            log_report "OK: $filename (${filesize} bytes) from Wayback Machine"
            DOWNLOADED=$((DOWNLOADED + 1))
            return 0
        else
            echo -e "  ${YELLOW}WARNING${NC}: Wayback file invalid (${filesize} bytes, not a PDF)"
            rm -f "$dest"
        fi
    else
        echo -e "  ${RED}FAILED${NC}: Wayback Machine also failed"
    fi

    # All sources failed
    echo -e "  ${RED}ERROR${NC}: Could not download $filename from any source"
    log_report "ERROR: $filename - all download sources failed"
    ERRORS=$((ERRORS + 1))
    return 0  # Don't exit script on individual failure
}

echo "============================================"
echo "SurvivalRAG Tier 1 Document Download"
echo "============================================"
echo ""
echo "Target directory: $ORIGINALS_DIR"
echo ""

# ============================================
# MILITARY DOCUMENTS (Distribution Statement A)
# ============================================
echo "--- Military Documents ---"
echo ""

# FM 21-76: US Army Survival Manual (1992)
download_file \
    "$ORIGINALS_DIR/military/FM-21-76.pdf" \
    "https://www.bits.de/NRANEU/others/amd-us-archive/FM21-76(92).pdf" \
    "https://archive.org/download/Fm21-76SurvivalManual/Fm21-76SurvivalManual.pdf"

# FM 21-76-1: Survival, Evasion, and Recovery (1999)
download_file \
    "$ORIGINALS_DIR/military/FM-21-76-1.pdf" \
    "https://irp.fas.org/doddir/army/fm21-76-1.pdf" \
    "https://trueprepper.com/wp-content/uploads/2023/03/FM-21-76-1-Survival-Evasion-and-Recovery-Multiservice-Procedures.pdf"

# FM 21-10 / MCRP 4-11.1D: Field Hygiene and Sanitation (2000)
download_file \
    "$ORIGINALS_DIR/military/FM-21-10.pdf" \
    "https://www.marines.mil/Portals/1/Publications/MCRP%204-11.1D%20Field%20Hygiene%20and%20Sanitation.pdf" \
    "https://archive.org/download/FM21-10_2000/FM21-10_2000.pdf"

# FM 4-25.11: First Aid (2002)
download_file \
    "$ORIGINALS_DIR/military/FM-4-25-11.pdf" \
    "https://www.globalsecurity.org/military/library/policy/army/fm/4-25-11/fm4-25-11.pdf" \
    "https://archive.org/download/FM4-25.11/FM4-25.11.pdf"

# TC 4-02.3: Field Hygiene and Sanitation (2015, successor to FM 21-10)
download_file \
    "$ORIGINALS_DIR/military/TC-4-02-3.pdf" \
    "https://armypubs.army.mil/epubs/DR_pubs/DR_a/pdf/web/tc4_02x3.pdf" \
    ""

# TC 4-02.1: First Aid (2016, successor to FM 4-25.11)
download_file \
    "$ORIGINALS_DIR/military/TC-4-02-1.pdf" \
    "https://rdl.train.army.mil/catalog-ws/view/100.ATSC/B0A32FAD-8C7A-44A6-8FF4-F754A32F1C30-1453986206542/tc4-02.1wc1x2.pdf" \
    ""

echo ""

# ============================================
# FEMA DOCUMENTS (US Government work)
# ============================================
echo "--- FEMA Documents ---"
echo ""

# Are You Ready? An In-Depth Guide to Citizen Preparedness
download_file \
    "$ORIGINALS_DIR/fema/are-you-ready.pdf" \
    "https://www.fema.gov/pdf/areyouready/areyouready_full.pdf" \
    "https://web.archive.org/web/2020id_/https://www.fema.gov/pdf/areyouready/areyouready_full.pdf"

# Food and Water in an Emergency
download_file \
    "$ORIGINALS_DIR/fema/food-and-water-in-emergency.pdf" \
    "https://www.fema.gov/pdf/library/f&web.pdf" \
    ""

# How to Build a Kit for Emergencies
download_file \
    "$ORIGINALS_DIR/fema/how-to-build-emergency-kit.pdf" \
    "https://www.fema.gov/print/pdf/node/503732" \
    ""

# Basic Preparedness
download_file \
    "$ORIGINALS_DIR/fema/basic-preparedness.pdf" \
    "https://www.fema.gov/pdf/areyouready/basic_preparedness.pdf" \
    ""

echo ""

# ============================================
# CDC DOCUMENTS (US Government work)
# ============================================
echo "--- CDC Documents ---"
echo ""

# Emergency Wound Care After a Natural Disaster
download_file \
    "$ORIGINALS_DIR/cdc/emergency-wound-care.pdf" \
    "https://www.cdc.gov/disasters/hurricanes/pdf/woundcare.pdf" \
    "https://stacks.cdc.gov/view/cdc/25434/cdc_25434_DS1.pdf"

# How to Make Water Safe in an Emergency
download_file \
    "$ORIGINALS_DIR/cdc/make-water-safe-emergency.pdf" \
    "https://www.cdc.gov/water-emergency/media/pdfs/make-water-safe-during-emergency-p.pdf" \
    ""

# Use Safe Water During an Emergency
download_file \
    "$ORIGINALS_DIR/cdc/use-safe-water-emergency.pdf" \
    "https://www.cdc.gov/water-emergency/media/pdfs/334749-B_UseSafeWater-OnePager-508.pdf" \
    ""

# Keep Food and Water Safe After a Natural Disaster
download_file \
    "$ORIGINALS_DIR/cdc/keep-food-water-safe.pdf" \
    "https://stacks.cdc.gov/view/cdc/25410/cdc_25410_DS1.pdf" \
    ""

# Keep Food Safe After a Disaster or Emergency (web page - attempt capture)
# This is a web page, not a PDF. Attempt download; if it fails or returns HTML, note it.
echo -e "NOTE: CDC 'Keep Food Safe' is a web page, not a PDF."
echo -e "  Attempting to download HTML and noting for manual PDF capture..."
if command -v wkhtmltopdf &>/dev/null; then
    echo -e "  wkhtmltopdf found, attempting conversion..."
    if wkhtmltopdf "https://www.cdc.gov/food-safety/foods/keep-food-safe-after-emergency.html" "$ORIGINALS_DIR/cdc/keep-food-safe-disaster.pdf" 2>/dev/null; then
        filesize=$(wc -c < "$ORIGINALS_DIR/cdc/keep-food-safe-disaster.pdf" | tr -d ' ')
        echo -e "  ${GREEN}OK${NC}: keep-food-safe-disaster.pdf (${filesize} bytes) [web capture]"
        log_report "OK: keep-food-safe-disaster.pdf (${filesize} bytes) from web capture via wkhtmltopdf"
        DOWNLOADED=$((DOWNLOADED + 1))
    else
        echo -e "  ${YELLOW}WARNING${NC}: wkhtmltopdf conversion failed"
        log_report "WARNING: keep-food-safe-disaster.pdf - wkhtmltopdf conversion failed. Manual PDF capture needed."
        log_report "  Source: https://www.cdc.gov/food-safety/foods/keep-food-safe-after-emergency.html"
    fi
else
    echo -e "  ${YELLOW}NOTE${NC}: wkhtmltopdf not available. Manual PDF capture needed for this document."
    log_report "NOTE: keep-food-safe-disaster.pdf - wkhtmltopdf not installed. Manual PDF capture needed."
    log_report "  Source: https://www.cdc.gov/food-safety/foods/keep-food-safe-after-emergency.html"
    log_report "  Instructions: Open URL in browser, Print -> Save as PDF -> save to sources/originals/cdc/keep-food-safe-disaster.pdf"
fi
TOTAL=$((TOTAL + 1))

# All-Hazards Preparedness Guide
download_file \
    "$ORIGINALS_DIR/cdc/all-hazards-preparedness-guide.pdf" \
    "https://stacks.cdc.gov/view/cdc/12007/cdc_12007_DS1.pdf" \
    ""

# Public Health Emergency Response Guide v2.0
download_file \
    "$ORIGINALS_DIR/cdc/public-health-emergency-response.pdf" \
    "https://stacks.cdc.gov/view/cdc/5972/cdc_5972_DS1.pdf" \
    ""

echo ""

# ============================================
# GENERATE CHECKSUMS
# ============================================
echo "--- Generating SHA-256 Checksums ---"
echo ""

# Generate checksums for all downloaded PDFs
# Use find to handle nested directories properly
> "$CHECKSUMS_FILE"  # Clear/create file

for pdf in $(find "$ORIGINALS_DIR" -name "*.pdf" -type f | sort); do
    # Get path relative to sources/ directory for portability
    rel_path="${pdf#$SOURCES_DIR/}"
    checksum=$(sha256sum "$pdf" | cut -d' ' -f1)
    echo "$checksum  $rel_path" >> "$CHECKSUMS_FILE"
    echo "  $checksum  $rel_path"
done

echo ""

# ============================================
# SUMMARY
# ============================================
echo "============================================"
echo "Download Summary"
echo "============================================"
echo "Total documents:  $TOTAL"
echo "Downloaded:       $DOWNLOADED"
echo "Skipped (exist):  $SKIPPED"
echo "Errors:           $ERRORS"
echo ""

# Count actual files
MILITARY_COUNT=$(find "$ORIGINALS_DIR/military" -name "*.pdf" -type f | wc -l | tr -d ' ')
FEMA_COUNT=$(find "$ORIGINALS_DIR/fema" -name "*.pdf" -type f | wc -l | tr -d ' ')
CDC_COUNT=$(find "$ORIGINALS_DIR/cdc" -name "*.pdf" -type f | wc -l | tr -d ' ')
TOTAL_FILES=$((MILITARY_COUNT + FEMA_COUNT + CDC_COUNT))

echo "Files on disk:"
echo "  Military: $MILITARY_COUNT"
echo "  FEMA:     $FEMA_COUNT"
echo "  CDC:      $CDC_COUNT"
echo "  Total:    $TOTAL_FILES"
echo ""

log_report ""
log_report "Summary: $DOWNLOADED downloaded, $SKIPPED skipped, $ERRORS errors out of $TOTAL total"
log_report "Files on disk: Military=$MILITARY_COUNT, FEMA=$FEMA_COUNT, CDC=$CDC_COUNT, Total=$TOTAL_FILES"

if [ "$ERRORS" -gt 0 ]; then
    echo -e "${YELLOW}WARNING: $ERRORS document(s) could not be downloaded. See download-report.txt${NC}"
    echo ""
fi

echo "Checksums written to: $CHECKSUMS_FILE"
echo "Download report: $REPORT_FILE"
echo "Done."
