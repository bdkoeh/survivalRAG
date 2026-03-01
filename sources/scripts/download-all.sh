#!/usr/bin/env bash
# download-all.sh - Download all Tier 1 source documents for SurvivalRAG
#
# Idempotent: skips files that already exist.
# Uses curl with retry logic and fallback URLs.
# Generates SHA-256 checksums after all downloads complete.
#
# Usage: bash sources/scripts/download-all.sh
#
# Expected output directory: sources/originals/{military,usaf,fema,cdc,epa,usda,noaa,uscg,nps,dhs,hhs}/

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

# Capture a web page as PDF using wkhtmltopdf or log manual capture instructions
# Usage: web_capture <dest_path> <url> <title>
web_capture() {
    local dest="$1"
    local url="$2"
    local title="$3"
    local filename
    filename="$(basename "$dest")"

    TOTAL=$((TOTAL + 1))

    # Skip if file already exists and is > 1KB
    if [ -f "$dest" ]; then
        local filesize
        filesize=$(wc -c < "$dest" | tr -d ' ')
        if [ "$filesize" -gt 1024 ]; then
            echo -e "${YELLOW}SKIP${NC} (exists, ${filesize} bytes): $filename"
            log_report "SKIP: $filename (exists, ${filesize} bytes)"
            SKIPPED=$((SKIPPED + 1))
            return 0
        else
            rm -f "$dest"
        fi
    fi

    mkdir -p "$(dirname "$dest")"

    echo -e "WEB CAPTURE: $title"
    echo -e "  URL: $url"

    # Try Chrome headless first (macOS path), then wkhtmltopdf
    local chrome_bin="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if [ -x "$chrome_bin" ]; then
        echo -e "  Chrome found, attempting headless PDF capture..."
        if "$chrome_bin" --headless --disable-gpu --no-sandbox --print-to-pdf="$dest" "$url" 2>/dev/null; then
            local filesize
            filesize=$(wc -c < "$dest" | tr -d ' ')
            if [ "$filesize" -gt 1024 ]; then
                echo -e "  ${GREEN}OK${NC}: $filename (${filesize} bytes) [chrome headless]"
                log_report "OK: $filename (${filesize} bytes) from web capture via Chrome headless"
                DOWNLOADED=$((DOWNLOADED + 1))
                return 0
            else
                echo -e "  ${YELLOW}WARNING${NC}: Chrome output too small (${filesize} bytes)"
                rm -f "$dest"
            fi
        else
            echo -e "  ${YELLOW}WARNING${NC}: Chrome headless capture failed"
        fi
    elif command -v wkhtmltopdf &>/dev/null; then
        echo -e "  wkhtmltopdf found, attempting conversion..."
        if wkhtmltopdf --quiet "$url" "$dest" 2>/dev/null; then
            local filesize
            filesize=$(wc -c < "$dest" | tr -d ' ')
            if [ "$filesize" -gt 1024 ]; then
                echo -e "  ${GREEN}OK${NC}: $filename (${filesize} bytes) [web capture]"
                log_report "OK: $filename (${filesize} bytes) from web capture via wkhtmltopdf"
                DOWNLOADED=$((DOWNLOADED + 1))
                return 0
            else
                echo -e "  ${YELLOW}WARNING${NC}: wkhtmltopdf output too small (${filesize} bytes)"
                rm -f "$dest"
            fi
        else
            echo -e "  ${YELLOW}WARNING${NC}: wkhtmltopdf conversion failed"
        fi
    fi

    echo -e "  ${YELLOW}NOTE${NC}: Manual PDF capture needed for $filename"
    log_report "NOTE: $filename - manual PDF capture needed"
    log_report "  Source: $url"
    log_report "  Instructions: Open URL in browser, Print -> Save as PDF -> save to $dest"
    return 0
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
web_capture \
    "$ORIGINALS_DIR/cdc/keep-food-safe-disaster.pdf" \
    "https://www.cdc.gov/food-safety/foods/keep-food-safe-after-emergency.html" \
    "CDC Keep Food Safe After Disaster"

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
# ADDITIONAL MILITARY DOCUMENTS (Distribution Statement A)
# ============================================
echo "--- Additional Military Documents ---"
echo ""

# TC 3-21.76: Ranger Handbook (2017)
download_file \
    "$ORIGINALS_DIR/military/TC-3-21-76.pdf" \
    "https://armypubs.army.mil/epubs/DR_pubs/DR_a/ARN3039-TC_3-21.76-000-WEB-1.pdf" \
    "https://archive.org/download/tc3-21-76/tc3-21-76.pdf"

# CALL 17-13: TCCC Handbook v5 (2017)
download_file \
    "$ORIGINALS_DIR/military/CALL-17-13.pdf" \
    "https://api.army.mil/e2/c/downloads/2023/01/19/31e03488/17-13-tactical-casualty-combat-care-handbook-v5-may-17-distro-a.pdf" \
    ""

# ATP 4-02.5: Casualty Care (2013)
download_file \
    "$ORIGINALS_DIR/military/ATP-4-02-5.pdf" \
    "https://armypubs.army.mil/epubs/DR_pubs/DR_a/ARN30121-ATP_4-02.5-001-WEB-3.pdf" \
    "https://rdl.train.army.mil/catalog-ws/view/100.ATSC/4A9AE0C8-9AC6-43F6-85FD-492A9F564E65-1368640415826/atp_4-02x5wc1.pdf"

# FM 3-25.26: Map Reading and Land Navigation (2001)
download_file \
    "$ORIGINALS_DIR/military/FM-3-25-26.pdf" \
    "https://irp.fas.org/doddir/army/fm3-25-26.pdf" \
    "https://www.globalsecurity.org/military/library/policy/army/fm/3-25-26/fm3-25-26_c1.pdf"

# FM 5-125: Rigging Techniques, Procedures, and Applications (2001)
download_file \
    "$ORIGINALS_DIR/military/FM-5-125.pdf" \
    "https://www.globalsecurity.org/military/library/policy/army/fm/5-125/fm5-125_c1.pdf" \
    "https://archive.org/download/RiggingTechniquesProceduresAndApplicationsFM51252001/FM5-125.pdf"

# TC 21-3: Cold Weather Survival (1986)
download_file \
    "$ORIGINALS_DIR/military/TC-21-3.pdf" \
    "https://armypubs.army.mil/epubs/DR_pubs/DR_a/NOCASE-TC_21-3-000-WEB-0.pdf" \
    "https://archive.org/download/milmanual-tc-21-3---soldiers-handbook-for-individual-operations-and-su/tc-21-3.pdf"

# ATTP 3-97.11 / MCRP 3-35.1D: Cold Region Operations (2011)
download_file \
    "$ORIGINALS_DIR/military/ATTP-3-97-11.pdf" \
    "https://www.marines.mil/portals/1/Publications/MCRP%203-35.1D%20Cold%20Region%20Operations.pdf" \
    ""

# ATP 3-90.97: Mountain and Cold Weather Operations (2016)
download_file \
    "$ORIGINALS_DIR/military/ATP-3-90-97.pdf" \
    "https://irp.fas.org/doddir/army/atp3-90-97.pdf" \
    "https://apps.dtic.mil/sti/pdfs/AD1013626.pdf"

# FM 3-97.6: Mountain Operations (2000)
download_file \
    "$ORIGINALS_DIR/military/FM-3-97-6.pdf" \
    "https://irp.fas.org/doddir/army/fm3-97-6.pdf" \
    "https://www.bits.de/NRANEU/others/amd-us-archive/FM3-97.6(00).pdf"

# FM 3-97.61: Military Mountaineering (2002)
download_file \
    "$ORIGINALS_DIR/military/FM-3-97-61.pdf" \
    "https://www.globalsecurity.org/military/library/policy/army/fm/3-97-61/fm3-97-61_c1_2003.pdf" \
    "https://archive.org/download/milmanual-fm-3-97.61-military-mountaineering/fm-3-97.61.pdf"

# FM 90-3: Desert Operations (1993)
download_file \
    "$ORIGINALS_DIR/military/FM-90-3.pdf" \
    "https://irp.fas.org/doddir/army/fm90-3.pdf" \
    "https://www.bits.de/NRANEU/others/amd-us-archive/FM90-3(93).pdf"

# FM 90-5: Jungle Operations (1982)
download_file \
    "$ORIGINALS_DIR/military/FM-90-5.pdf" \
    "https://irp.fas.org/doddir/army/fm90-5.pdf" \
    "https://archive.org/download/milmanual-fm-90-5-jungle-operations/fm-90-5.pdf"

# TC 21-21: Water Survival Training (1991)
download_file \
    "$ORIGINALS_DIR/military/TC-21-21.pdf" \
    "https://ia601500.us.archive.org/28/items/MManuals/WaterSurvivalTraining.pdf" \
    "https://www.elon.edu/assets/docs/rotc/TC%2021-21%20Water%20Survial%20Training.pdf"

# FM 4-25.12: Unit Field Sanitation Team (2002)
download_file \
    "$ORIGINALS_DIR/military/FM-4-25-12.pdf" \
    "https://usacac.army.mil/sites/default/files/misc/doctrine/CDG/cdg_resources/manuals/fm/fm4_25x12.pdf" \
    "https://ia801807.us.archive.org/35/items/FM4-25x12/FM4-25x12.pdf"

# FM 3-11.4: Multiservice Tactics for NBC Protection (2003)
download_file \
    "$ORIGINALS_DIR/military/FM-3-11-4.pdf" \
    "https://irp.fas.org/doddir/army/fm3-11-4.pdf" \
    "https://www.globalsecurity.org/wmd/library/policy/army/fm/3-11-4/fm3-11-4.pdf"

# FM 3-11.5: Multiservice CBRN Decontamination (2006)
download_file \
    "$ORIGINALS_DIR/military/FM-3-11-5.pdf" \
    "https://www.globalsecurity.org/wmd/library/policy/army/fm/3-11-5/fm-3-11-5.pdf" \
    "https://apps.dtic.mil/sti/tr/pdf/ADA523781.pdf"

# FM 7-22: Holistic Health and Fitness (2020)
download_file \
    "$ORIGINALS_DIR/military/FM-7-22.pdf" \
    "https://armypubs.army.mil/epubs/DR_pubs/DR_a/ARN30714-FM_7-22-000-WEB-1.pdf" \
    "https://home.army.mil/cavazos/5517/2115/1094/FM_7-22.pdf"

echo ""

# ============================================
# USAF DOCUMENTS (Distribution Statement A)
# ============================================
echo "--- USAF Documents ---"
echo ""

# AFH 10-644: USAF SERE Handbook (2017)
download_file \
    "$ORIGINALS_DIR/usaf/AFH-10-644.pdf" \
    "https://static.e-publishing.af.mil/production/1/af_a3/publication/afh10-644/afh10-644.pdf" \
    "https://archive.org/download/AFH10644SurvivalEvasionResistanceEscapeSERE/AFH10644.pdf"

echo ""

# ============================================
# ADDITIONAL FEMA DOCUMENTS (US Government work)
# ============================================
echo "--- Additional FEMA Documents ---"
echo ""

# CERT Basic Training Manual (2019)
download_file \
    "$ORIGINALS_DIR/fema/cert-basic-training.pdf" \
    "https://www.ready.gov/sites/default/files/2019.CERT_.Basic_.PM_FINAL_508c.pdf" \
    ""

# Nuclear Detonation Planning Guide
download_file \
    "$ORIGINALS_DIR/fema/nuclear-detonation-planning.pdf" \
    "https://www.fema.gov/sites/default/files/documents/fema_nuc-detonation-planning-guide.pdf" \
    ""

# Shelter-in-Place Nuclear Guidance
download_file \
    "$ORIGINALS_DIR/fema/shelter-in-place-nuclear.pdf" \
    "https://www.fema.gov/sites/default/files/documents/fema_shelter-in-place_guidance-nuclear.pdf" \
    ""

# 72-Hour Nuclear Response
download_file \
    "$ORIGINALS_DIR/fema/72-hour-nuclear-response.pdf" \
    "https://www.fema.gov/sites/default/files/documents/fema_oet-72-hour-nuclear-detonation-response-guidance.pdf" \
    ""

# Full Suite Hazard Info Sheets
download_file \
    "$ORIGINALS_DIR/fema/hazard-info-sheets.pdf" \
    "https://www.ready.gov/sites/default/files/2025-02/fema_full-suite-hazard-info-sheets.pdf" \
    ""

# Nuclear Explosion Info Sheet
download_file \
    "$ORIGINALS_DIR/fema/nuclear-explosion-info.pdf" \
    "https://www.ready.gov/sites/default/files/2020-03/nuclear-explosion-information-sheet.pdf" \
    ""

# Preparing for Disaster (Disabilities)
download_file \
    "$ORIGINALS_DIR/fema/preparing-disaster-disabilities.pdf" \
    "https://www.fema.gov/pdf/library/pfd_all.pdf" \
    "https://www.fema.gov/pdf/library/pfd.pdf"

echo ""

# ============================================
# ADDITIONAL CDC DOCUMENTS (US Government work)
# ============================================
echo "--- Additional CDC Documents ---"
echo ""

# Extreme Heat Prevention Guide (PDF from CDC Stacks)
download_file \
    "$ORIGINALS_DIR/cdc/extreme-heat-prevention.pdf" \
    "https://stacks.cdc.gov/view/cdc/7023/cdc_7023_DS1.pdf" \
    ""

# Preventing Diarrheal Illness After Disaster (web capture)
web_capture \
    "$ORIGINALS_DIR/cdc/preventing-diarrheal-illness.pdf" \
    "https://www.cdc.gov/water-emergency/communication-resources/fact-sheet-preventing-diarrheal-illness-after-a-disaster.html" \
    "CDC Preventing Diarrheal Illness After Disaster"

# Personal Hygiene During Emergency (web capture)
web_capture \
    "$ORIGINALS_DIR/cdc/personal-hygiene-emergency.pdf" \
    "https://www.cdc.gov/water-emergency/safety/guidelines-for-personal-hygiene-during-an-emergency.html" \
    "CDC Personal Hygiene During Emergency"

# Venomous Snakes (web capture)
web_capture \
    "$ORIGINALS_DIR/cdc/venomous-snakes.pdf" \
    "https://www.cdc.gov/niosh/outdoor-workers/about/venomous-snakes.html" \
    "CDC Venomous Snakes"

# Venomous Spiders (web capture)
web_capture \
    "$ORIGINALS_DIR/cdc/venomous-spiders.pdf" \
    "https://www.cdc.gov/niosh/outdoor-workers/about/venomous-spiders.html" \
    "CDC Venomous Spiders"

# Hypothermia Prevention (web capture)
web_capture \
    "$ORIGINALS_DIR/cdc/hypothermia-prevention.pdf" \
    "https://www.cdc.gov/winter-weather/prevention/index.html" \
    "CDC Hypothermia Prevention"

# Carbon Monoxide Poisoning Prevention (web capture)
web_capture \
    "$ORIGINALS_DIR/cdc/carbon-monoxide-prevention.pdf" \
    "https://www.cdc.gov/carbon-monoxide/about/index.html" \
    "CDC Carbon Monoxide Poisoning Prevention"

# Tetanus Wound Management (web capture)
web_capture \
    "$ORIGINALS_DIR/cdc/tetanus-wound-management.pdf" \
    "https://www.cdc.gov/tetanus/hcp/clinical-guidance/index.html" \
    "CDC Tetanus Wound Management"

echo ""

# ============================================
# EPA DOCUMENTS (US Government work)
# ============================================
echo "--- EPA Documents ---"
echo ""

# Emergency Disinfection of Drinking Water
download_file \
    "$ORIGINALS_DIR/epa/emergency-disinfection-drinking-water.pdf" \
    "https://www.epa.gov/sites/default/files/2017-09/documents/emergency_disinfection_of_drinking_water_sept2017.pdf" \
    ""

echo ""

# ============================================
# USDA DOCUMENTS (US Government work)
# ============================================
echo "--- USDA Documents ---"
echo ""

# Complete Guide to Home Canning - Introduction
download_file \
    "$ORIGINALS_DIR/usda/home-canning-intro.pdf" \
    "https://nchfp.uga.edu/papers/guide/INTRO_HomeCanrev0715.pdf" \
    ""

# Complete Guide to Home Canning - Guide 1: Principles of Home Canning
download_file \
    "$ORIGINALS_DIR/usda/home-canning-guide1.pdf" \
    "https://nchfp.uga.edu/papers/guide/GUIDE01_HomeCan_rev0715.pdf" \
    ""

# Complete Guide to Home Canning - Guide 2: Canning Fruit
download_file \
    "$ORIGINALS_DIR/usda/home-canning-guide2.pdf" \
    "https://nchfp.uga.edu/papers/guide/GUIDE02_HomeCan_rev0715.pdf" \
    ""

# Complete Guide to Home Canning - Guide 3: Canning Tomatoes
download_file \
    "$ORIGINALS_DIR/usda/home-canning-guide3.pdf" \
    "https://nchfp.uga.edu/papers/guide/GUIDE03_HomeCan_rev0715.pdf" \
    ""

# Complete Guide to Home Canning - Guide 4: Canning Vegetables
download_file \
    "$ORIGINALS_DIR/usda/home-canning-guide4.pdf" \
    "https://nchfp.uga.edu/papers/guide/GUIDE04_HomeCan_rev0715.pdf" \
    ""

# Complete Guide to Home Canning - Guide 5: Canning Poultry, Red Meats, and Seafoods
download_file \
    "$ORIGINALS_DIR/usda/home-canning-guide5.pdf" \
    "https://nchfp.uga.edu/papers/guide/GUIDE05_HomeCan_rev0715.pdf" \
    ""

# Complete Guide to Home Canning - Guide 6: Canning Fermented and Pickled Foods
download_file \
    "$ORIGINALS_DIR/usda/home-canning-guide6.pdf" \
    "https://nchfp.uga.edu/papers/guide/GUIDE06_HomeCan_rev0715.pdf" \
    ""

# Complete Guide to Home Canning - Guide 7: Canning Jams and Jellies
download_file \
    "$ORIGINALS_DIR/usda/home-canning-guide7.pdf" \
    "https://nchfp.uga.edu/papers/guide/GUIDE07_HomeCan_rev0715.pdf" \
    ""

# USDA Forest Service: Wild Edible Mushrooms (PNW-GTR-309)
download_file \
    "$ORIGINALS_DIR/usda/foraging-wild-plants.pdf" \
    "https://www.fs.usda.gov/pnw/pubs/pnw_gtr309.pdf" \
    ""

# USDA FSIS: Keep Food Safe During Emergencies (web capture)
web_capture \
    "$ORIGINALS_DIR/usda/keep-food-safe-emergencies.pdf" \
    "https://www.fsis.usda.gov/food-safety/safe-food-handling-and-preparation/emergencies/keep-your-food-safe-during-emergencies" \
    "USDA FSIS Keep Food Safe During Emergencies"

echo ""

# ============================================
# NOAA / NWS DOCUMENTS (US Government work)
# ============================================
echo "--- NOAA Documents ---"
echo ""

# Tornado Safety Brochure
download_file \
    "$ORIGINALS_DIR/noaa/tornado-safety.pdf" \
    "https://www.weather.gov/media/owlie/Tornado-Brochure-062717.pdf" \
    ""

# Thunderstorm Safety Brochure
download_file \
    "$ORIGINALS_DIR/noaa/thunderstorm-safety.pdf" \
    "https://www.weather.gov/media/safety/Thunderstorm-brochure17.pdf" \
    "https://www.weather.gov/media/owlie/3-fold-Brochure-Thunderstorm-Safety-08-07-18-FINAL.pdf"

# Wind Chill Chart
download_file \
    "$ORIGINALS_DIR/noaa/wind-chill-chart.pdf" \
    "https://www.weather.gov/media/safety/windchillchart3.pdf" \
    ""

# Heat Index Chart
download_file \
    "$ORIGINALS_DIR/noaa/heat-index-chart.pdf" \
    "https://www.weather.gov/media/unr/heatindex.pdf" \
    "https://www.noaa.gov/sites/default/files/2022-05/heatindex_chart_rh.pdf"

echo ""

# ============================================
# USCG DOCUMENTS (US Government work)
# ============================================
echo "--- USCG Documents ---"
echo ""

# Cold Water Survival Guide
download_file \
    "$ORIGINALS_DIR/uscg/cold-water-survival.pdf" \
    "https://www.dco.uscg.mil/Portals/9/DCO%20Documents/5p/CG-5PC/CG-CVC/CVC3/notice/flyers/Cold_Water_Survival_Hypothermia.pdf" \
    "https://www.dco.uscg.mil/Portals/9/CG-5R/nsarc/MSC1Circ1185a%20-%20Guide%20to%20Cold%20Water%20Survival%20(113012).pdf"

echo ""

# ============================================
# NPS DOCUMENTS (US Government work)
# ============================================
echo "--- NPS Documents ---"
echo ""

# Bear Safety (web capture)
web_capture \
    "$ORIGINALS_DIR/nps/bear-safety.pdf" \
    "https://www.nps.gov/subjects/bears/safety.htm" \
    "NPS Bear Safety"

# Mountain Lion Safety (web capture)
web_capture \
    "$ORIGINALS_DIR/nps/mountain-lion-safety.pdf" \
    "https://www.nps.gov/articles/mountain-lion-safety.htm" \
    "NPS Mountain Lion Safety"

# Ten Essentials (web capture)
web_capture \
    "$ORIGINALS_DIR/nps/ten-essentials.pdf" \
    "https://www.nps.gov/articles/10essentials.htm" \
    "NPS Ten Essentials"

echo ""

# ============================================
# DHS DOCUMENTS (US Government work)
# ============================================
echo "--- DHS Documents ---"
echo ""

# Stop the Bleed Tourniquet Guide
download_file \
    "$ORIGINALS_DIR/dhs/stop-the-bleed.pdf" \
    "https://www.dhs.gov/sites/default/files/publications/STB_Applying_Tourniquet_08-06-2018_0.pdf" \
    ""

echo ""

# ============================================
# HHS DOCUMENTS (US Government work)
# ============================================
echo "--- HHS Documents ---"
echo ""

# Psychological First Aid: Field Operations Guide (2nd Edition)
download_file \
    "$ORIGINALS_DIR/hhs/psychological-first-aid.pdf" \
    "https://www.ptsd.va.gov/disaster_events/for_providers/PFA/PFA_2ndEditionwithappendices.pdf" \
    ""

# REMM Radiation Emergency Medical Management (web capture)
web_capture \
    "$ORIGINALS_DIR/hhs/remm-radiation-emergency.pdf" \
    "https://remm.hhs.gov/" \
    "HHS REMM Radiation Emergency Medical Management"

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

# Count actual files (dynamic subdirectory scanning)
TOTAL_FILES=0
echo "Files on disk:"
DISK_SUMMARY=""
for subdir in $(find "$ORIGINALS_DIR" -mindepth 1 -maxdepth 1 -type d | sort); do
    count=$(find "$subdir" -name "*.pdf" -type f | wc -l | tr -d ' ')
    name=$(basename "$subdir")
    echo "  $name: $count"
    DISK_SUMMARY="${DISK_SUMMARY}${name}=${count}, "
    TOTAL_FILES=$((TOTAL_FILES + count))
done
echo "  Total:    $TOTAL_FILES"
echo ""

log_report ""
log_report "Summary: $DOWNLOADED downloaded, $SKIPPED skipped, $ERRORS errors out of $TOTAL total"
log_report "Files on disk: ${DISK_SUMMARY}Total=$TOTAL_FILES"

if [ "$ERRORS" -gt 0 ]; then
    echo -e "${YELLOW}WARNING: $ERRORS document(s) could not be downloaded. See download-report.txt${NC}"
    echo ""
fi

echo "Checksums written to: $CHECKSUMS_FILE"
echo "Download report: $REPORT_FILE"
echo "Done."
