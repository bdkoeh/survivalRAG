#!/usr/bin/env bash
# validate-manifests.sh - Bash-based manifest validation
# Performs the same checks as validate-manifests.py for environments without Python/PyYAML
# Usage: bash sources/scripts/validate-manifests.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCES_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFESTS_DIR="$SOURCES_DIR/manifests"
ORIGINALS_DIR="$SOURCES_DIR/originals"
CHECKSUMS_FILE="$SOURCES_DIR/checksums.sha256"
EXCLUDED_FILE="$SOURCES_DIR/excluded/EXCLUDED.md"

ERRORS=0
CHECKED=0

err() {
    echo "  ERROR: $1"
    ERRORS=$((ERRORS + 1))
}

ok() {
    echo "  OK: $1"
}

echo "============================================================"
echo "SurvivalRAG Provenance Manifest Validation (bash)"
echo "============================================================"
echo ""

# --- Check prerequisites ---
if [ ! -d "$MANIFESTS_DIR" ]; then
    echo "FATAL: Manifests directory not found: $MANIFESTS_DIR"
    exit 1
fi

if [ ! -f "$CHECKSUMS_FILE" ]; then
    err "Checksums file not found: $CHECKSUMS_FILE"
fi

MANIFEST_COUNT=$(ls "$MANIFESTS_DIR"/*.yaml 2>/dev/null | wc -l)
echo "Found $MANIFEST_COUNT manifest files"
echo ""

# --- Required fields check (YAML parsed with grep/awk) ---
echo "--- Schema Completeness ---"

REQUIRED_TOP="document: source: licensing: content: processing:"
REQUIRED_DOC="title: file_name: file_sha256:"
REQUIRED_SRC="primary_url: publisher:"
REQUIRED_LIC="license_type: distribution_statement: verification_date: verification_method:"
REQUIRED_CONTENT="categories: tier:"
REQUIRED_PROC="download_date:"

MANIFEST_FILENAMES=()

for manifest in "$MANIFESTS_DIR"/*.yaml; do
    basename=$(basename "$manifest")
    CHECKED=$((CHECKED + 1))
    manifest_ok=true

    # Check top-level keys
    for key in $REQUIRED_TOP; do
        if ! grep -q "^${key}" "$manifest" 2>/dev/null; then
            err "MISSING top-level key '$key' in $basename"
            manifest_ok=false
        fi
    done

    # Check document section fields
    for key in $REQUIRED_DOC; do
        if ! grep -q "  ${key}" "$manifest" 2>/dev/null; then
            err "MISSING document.$key in $basename"
            manifest_ok=false
        fi
    done

    # Check source section fields
    for key in $REQUIRED_SRC; do
        if ! grep -q "  ${key}" "$manifest" 2>/dev/null; then
            err "MISSING source.$key in $basename"
            manifest_ok=false
        fi
    done

    # Check licensing section fields
    for key in $REQUIRED_LIC; do
        if ! grep -q "  ${key}" "$manifest" 2>/dev/null; then
            err "MISSING licensing.$key in $basename"
            manifest_ok=false
        fi
    done

    # Check content section fields
    for key in $REQUIRED_CONTENT; do
        if ! grep -q "  ${key}" "$manifest" 2>/dev/null; then
            err "MISSING content.$key in $basename"
            manifest_ok=false
        fi
    done

    # Check categories is non-empty (has at least one "- " entry after categories:)
    if ! grep -A1 "  categories:" "$manifest" | grep -q "    - "; then
        err "EMPTY categories list in $basename"
        manifest_ok=false
    fi

    # Check tier is 1
    tier_val=$(grep "  tier:" "$manifest" 2>/dev/null | head -1 | awk '{print $2}')
    if [ -n "$tier_val" ] && [ "$tier_val" != "1" ]; then
        err "WRONG tier=$tier_val in $basename (expected 1)"
        manifest_ok=false
    fi

    # Check processing section fields
    for key in $REQUIRED_PROC; do
        if ! grep -q "  ${key}" "$manifest" 2>/dev/null; then
            err "MISSING processing.$key in $basename"
            manifest_ok=false
        fi
    done

    # Extract file_name and file_sha256
    file_name=$(grep "  file_name:" "$manifest" | head -1 | sed 's/.*file_name: *"\{0,1\}\([^"]*\)"\{0,1\}/\1/' | tr -d '"' | xargs)
    file_sha256=$(grep "  file_sha256:" "$manifest" | head -1 | sed 's/.*file_sha256: *"\{0,1\}\([^"]*\)"\{0,1\}/\1/' | tr -d '"' | xargs)

    MANIFEST_FILENAMES+=("$file_name")

    # Cross-reference: file exists on disk
    found_path=""
    for subdir in military fema cdc; do
        candidate="$ORIGINALS_DIR/$subdir/$file_name"
        if [ -f "$candidate" ]; then
            found_path="$candidate"
            break
        fi
    done

    if [ -z "$found_path" ]; then
        err "FILE NOT FOUND: $file_name (referenced in $basename)"
        manifest_ok=false
    else
        # Cross-reference: SHA-256 matches checksums file
        if [ -n "$file_sha256" ] && [ -f "$CHECKSUMS_FILE" ]; then
            checksum_line=$(grep "$file_name" "$CHECKSUMS_FILE" 2>/dev/null || true)
            if [ -n "$checksum_line" ]; then
                checksum_val=$(echo "$checksum_line" | awk '{print $1}')
                if [ "$file_sha256" != "$checksum_val" ]; then
                    err "CHECKSUM MISMATCH in $basename: manifest=$file_sha256 vs checksums.sha256=$checksum_val"
                    manifest_ok=false
                fi
            else
                err "NOT IN CHECKSUMS FILE: $file_name (referenced in $basename)"
                manifest_ok=false
            fi

            # Verify actual file hash
            actual_sha=$(sha256sum "$found_path" | awk '{print $1}')
            if [ "$file_sha256" != "$actual_sha" ]; then
                err "ACTUAL FILE HASH MISMATCH in $basename: manifest=$file_sha256 vs actual=$actual_sha"
                manifest_ok=false
            fi
        fi
    fi

    # Licensing verification
    publisher=$(grep "  publisher:" "$manifest" | head -1 | sed 's/.*publisher: *"\{0,1\}\([^"]*\)"\{0,1\}/\1/' | tr -d '"' | xargs)
    dist_stmt=$(grep "  distribution_statement:" "$manifest" | head -1)
    license_type=$(grep "  license_type:" "$manifest" | head -1)

    case "$publisher" in
        "Department of the Army")
            if ! echo "$dist_stmt" | grep -qi "Approved for public release\|Distribution Statement A"; then
                err "LICENSING: Military doc $basename missing 'Approved for public release' or 'Distribution Statement A'"
                manifest_ok=false
            fi
            ;;
        "FEMA"|"FEMA / American Red Cross"|"CDC")
            if ! echo "$license_type" | grep -qi "US Government Work\|Public Domain"; then
                err "LICENSING: Civilian doc $basename missing 'US Government Work' or 'Public Domain'"
                manifest_ok=false
            fi
            ;;
    esac

    if $manifest_ok; then
        ok "$basename"
    else
        echo "  FAILED: $basename"
    fi
done
echo ""

# --- Orphan check ---
echo "--- Orphan Check ---"

# Get all PDFs
ALL_PDFS=()
for subdir in military fema cdc; do
    subdir_path="$ORIGINALS_DIR/$subdir"
    if [ -d "$subdir_path" ]; then
        while IFS= read -r pdf; do
            if [ -f "$pdf" ]; then
                ALL_PDFS+=("$(basename "$pdf")")
            fi
        done < <(ls "$subdir_path"/*.pdf 2>/dev/null || true)
    fi
done

# Check for orphan PDFs (PDF without manifest)
orphan_pdfs=0
for pdf in "${ALL_PDFS[@]}"; do
    found=false
    for mf in "${MANIFEST_FILENAMES[@]}"; do
        if [ "$pdf" = "$mf" ]; then
            found=true
            break
        fi
    done
    if ! $found; then
        err "ORPHAN PDF (no manifest): $pdf"
        orphan_pdfs=$((orphan_pdfs + 1))
    fi
done
if [ $orphan_pdfs -eq 0 ]; then
    ok "No orphan PDFs"
fi

# Check for orphan manifests (manifest without PDF)
orphan_manifests=0
for mf in "${MANIFEST_FILENAMES[@]}"; do
    found=false
    for pdf in "${ALL_PDFS[@]}"; do
        if [ "$mf" = "$pdf" ]; then
            found=true
            break
        fi
    done
    if ! $found; then
        err "ORPHAN MANIFEST (no PDF): $mf"
        orphan_manifests=$((orphan_manifests + 1))
    fi
done
if [ $orphan_manifests -eq 0 ]; then
    ok "No orphan manifests"
fi
echo ""

# --- Excluded document cross-check ---
echo "--- Excluded Document Cross-Check ---"

for pattern in FM-3-05-70 ST-31-91B FM-3-50-3; do
    if [ -f "$MANIFESTS_DIR/${pattern}.yaml" ]; then
        err "EXCLUDED DOC HAS MANIFEST: ${pattern}.yaml should not exist"
    else
        ok "No manifest for $pattern"
    fi
done

if [ -f "$EXCLUDED_FILE" ]; then
    for designation in "FM 3-05.70" "ST 31-91B" "FM 3-50.3"; do
        if grep -q "$designation" "$EXCLUDED_FILE"; then
            ok "$designation documented in EXCLUDED.md"
        else
            err "EXCLUDED.md missing entry for: $designation"
        fi
    done
else
    err "EXCLUDED.md not found at $EXCLUDED_FILE"
fi
echo ""

# --- Summary ---
echo "============================================================"
if [ $ERRORS -gt 0 ]; then
    echo "RESULT: FAIL ($ERRORS errors)"
    exit 1
else
    echo "RESULT: PASS (all checks passed)"
    echo "  Manifests validated: $CHECKED"
    echo "  PDFs verified: ${#ALL_PDFS[@]}"
    echo "  Excluded documents: 3"
    exit 0
fi
