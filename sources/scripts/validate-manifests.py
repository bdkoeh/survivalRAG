#!/usr/bin/env python3
"""
Validate provenance manifests for SurvivalRAG source documents.

Checks:
1. Schema completeness - all required top-level and nested keys present
2. Cross-reference - file_name exists on disk, SHA-256 matches
3. Licensing verification - military docs have Dist Statement A, civilian docs have US Gov Work
4. Orphan check - every PDF has a manifest, every manifest has a PDF
5. Excluded document cross-check - no manifest for excluded documents

Requires: pip install pyyaml

Usage: python sources/scripts/validate-manifests.py
Exit code: 0 if all pass, 1 if any fail
"""

import glob
import hashlib
import os
import sys

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_DIR = os.path.join(SCRIPT_DIR, "..")
MANIFESTS_DIR = os.path.join(SOURCES_DIR, "manifests")
ORIGINALS_DIR = os.path.join(SOURCES_DIR, "originals")
CHECKSUMS_FILE = os.path.join(SOURCES_DIR, "checksums.sha256")
EXCLUDED_FILE = os.path.join(SOURCES_DIR, "excluded", "EXCLUDED.md")

# Known excluded document identifiers (should not have manifests)
EXCLUDED_DESIGNATIONS = ["FM 3-05.70", "ST 31-91B", "FM 3-50.3"]
EXCLUDED_FILE_PATTERNS = ["FM-3-05-70", "ST-31-91B", "FM-3-50-3"]

# Required schema fields
REQUIRED_TOP_LEVEL = ["document", "source", "licensing", "content", "processing"]
REQUIRED_DOCUMENT = ["title", "file_name", "file_sha256"]
REQUIRED_SOURCE = ["primary_url", "publisher"]
REQUIRED_LICENSING = ["license_type", "distribution_statement", "verification_date", "verification_method"]
REQUIRED_CONTENT = ["categories", "tier"]
REQUIRED_PROCESSING = ["download_date"]

# Publisher-to-type mapping for licensing checks
MILITARY_PUBLISHERS = ["Department of the Army"]
CIVILIAN_PUBLISHERS = ["FEMA", "FEMA / American Red Cross", "CDC"]


def load_checksums(checksums_file):
    """Load SHA-256 checksums from checksums file."""
    checksums = {}
    if not os.path.exists(checksums_file):
        return checksums
    with open(checksums_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) == 2:
                sha256, filepath = parts
                # Normalize path separators and extract just the filename
                filename = os.path.basename(filepath.strip().replace("\\", "/"))
                checksums[filename] = sha256
    return checksums


def compute_sha256(filepath):
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def find_pdf(file_name, originals_dir):
    """Find a PDF file across subdirectories of originals/."""
    for subdir in ["military", "fema", "cdc"]:
        candidate = os.path.join(originals_dir, subdir, file_name)
        if os.path.exists(candidate):
            return candidate
    return None


def get_all_pdfs(originals_dir):
    """Get all PDF files in originals/ subdirectories."""
    pdfs = set()
    for subdir in ["military", "fema", "cdc"]:
        subdir_path = os.path.join(originals_dir, subdir)
        if os.path.isdir(subdir_path):
            for f in os.listdir(subdir_path):
                if f.lower().endswith(".pdf"):
                    pdfs.add(f)
    return pdfs


def validate_manifest(filepath, checksums, errors):
    """Validate a single manifest file. Returns manifest data or None."""
    basename = os.path.basename(filepath)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        errors.append(f"PARSE ERROR in {basename}: {e}")
        return None

    if not isinstance(data, dict):
        errors.append(f"INVALID in {basename}: root element is not a mapping")
        return None

    # Check top-level keys
    for key in REQUIRED_TOP_LEVEL:
        if key not in data:
            errors.append(f"MISSING KEY '{key}' in {basename}")

    # Check document section
    doc = data.get("document", {}) or {}
    for field in REQUIRED_DOCUMENT:
        if field not in doc:
            errors.append(f"MISSING document.{field} in {basename}")

    # Check source section
    src = data.get("source", {}) or {}
    for field in REQUIRED_SOURCE:
        if field not in src:
            errors.append(f"MISSING source.{field} in {basename}")

    # Check licensing section
    lic = data.get("licensing", {}) or {}
    for field in REQUIRED_LICENSING:
        if field not in lic:
            errors.append(f"MISSING licensing.{field} in {basename}")

    # Check content section
    content = data.get("content", {}) or {}
    for field in REQUIRED_CONTENT:
        if field not in content:
            errors.append(f"MISSING content.{field} in {basename}")

    # Categories must be non-empty list
    cats = content.get("categories", [])
    if not isinstance(cats, list) or len(cats) == 0:
        errors.append(f"EMPTY categories list in {basename}")

    # Tier must be 1
    tier = content.get("tier")
    if tier is not None and tier != 1:
        errors.append(f"WRONG tier={tier} in {basename} (expected 1)")

    # Check processing section
    proc = data.get("processing", {}) or {}
    for field in REQUIRED_PROCESSING:
        if field not in proc:
            errors.append(f"MISSING processing.{field} in {basename}")

    # Cross-reference: file exists on disk
    file_name = doc.get("file_name", "")
    if file_name:
        pdf_path = find_pdf(file_name, ORIGINALS_DIR)
        if pdf_path is None:
            errors.append(f"FILE NOT FOUND: {file_name} (referenced in {basename})")
        else:
            # Cross-reference: SHA-256 matches checksums file
            manifest_sha = doc.get("file_sha256", "")
            if manifest_sha:
                if file_name in checksums:
                    if manifest_sha != checksums[file_name]:
                        errors.append(
                            f"CHECKSUM MISMATCH in {basename}: "
                            f"manifest={manifest_sha[:16]}... "
                            f"checksums.sha256={checksums[file_name][:16]}..."
                        )
                else:
                    errors.append(f"NOT IN CHECKSUMS FILE: {file_name} (referenced in {basename})")

                # Verify actual file hash
                actual_sha = compute_sha256(pdf_path)
                if manifest_sha != actual_sha:
                    errors.append(
                        f"ACTUAL FILE HASH MISMATCH in {basename}: "
                        f"manifest={manifest_sha[:16]}... "
                        f"actual={actual_sha[:16]}..."
                    )

    # Licensing verification
    publisher = src.get("publisher", "")
    dist_stmt = lic.get("distribution_statement", "")
    license_type = lic.get("license_type", "")

    if publisher in MILITARY_PUBLISHERS:
        if not ("Approved for public release" in dist_stmt or "Distribution Statement A" in dist_stmt):
            errors.append(
                f"LICENSING: Military doc {basename} missing 'Approved for public release' "
                f"or 'Distribution Statement A' in distribution_statement"
            )
    elif publisher in CIVILIAN_PUBLISHERS:
        if not ("US Government Work" in license_type or "Public Domain" in license_type):
            errors.append(
                f"LICENSING: Civilian doc {basename} missing 'US Government Work' "
                f"or 'Public Domain' in license_type"
            )

    return data


def main():
    errors = []
    warnings = []

    print("=" * 60)
    print("SurvivalRAG Provenance Manifest Validation")
    print("=" * 60)
    print()

    # Load checksums
    checksums = load_checksums(CHECKSUMS_FILE)
    if not checksums:
        errors.append("CHECKSUMS FILE: Could not load checksums from " + CHECKSUMS_FILE)
    else:
        print(f"Loaded {len(checksums)} checksums from checksums.sha256")

    # Find all manifests
    manifest_files = sorted(glob.glob(os.path.join(MANIFESTS_DIR, "*.yaml")))
    if not manifest_files:
        errors.append("NO MANIFESTS FOUND in " + MANIFESTS_DIR)
        print(f"\nRESULT: FAIL ({len(errors)} errors)")
        sys.exit(1)

    print(f"Found {len(manifest_files)} manifest files")
    print()

    # Validate each manifest
    manifest_filenames = set()
    print("--- Schema & Cross-Reference Validation ---")
    for mf in manifest_files:
        basename = os.path.basename(mf)
        data = validate_manifest(mf, checksums, errors)
        if data:
            doc = data.get("document", {}) or {}
            file_name = doc.get("file_name", "")
            if file_name:
                manifest_filenames.add(file_name)
            print(f"  CHECKED: {basename}")
        else:
            print(f"  FAILED: {basename}")
    print()

    # Orphan check: PDFs without manifests
    print("--- Orphan Check ---")
    all_pdfs = get_all_pdfs(ORIGINALS_DIR)
    orphan_pdfs = all_pdfs - manifest_filenames
    orphan_manifests = manifest_filenames - all_pdfs

    if orphan_pdfs:
        for pdf in sorted(orphan_pdfs):
            errors.append(f"ORPHAN PDF (no manifest): {pdf}")
        print(f"  Orphan PDFs: {len(orphan_pdfs)}")
    else:
        print("  No orphan PDFs")

    if orphan_manifests:
        for mf in sorted(orphan_manifests):
            errors.append(f"ORPHAN MANIFEST (no PDF): {mf}")
        print(f"  Orphan manifests: {len(orphan_manifests)}")
    else:
        print("  No orphan manifests")
    print()

    # Excluded document cross-check
    print("--- Excluded Document Cross-Check ---")
    for pattern in EXCLUDED_FILE_PATTERNS:
        excluded_manifest = os.path.join(MANIFESTS_DIR, pattern + ".yaml")
        if os.path.exists(excluded_manifest):
            errors.append(f"EXCLUDED DOC HAS MANIFEST: {pattern}.yaml should not exist")
            print(f"  FAIL: {pattern}.yaml exists (should not)")
        else:
            print(f"  OK: No manifest for {pattern}")

    # Check EXCLUDED.md exists and covers required documents
    if os.path.exists(EXCLUDED_FILE):
        with open(EXCLUDED_FILE, "r", encoding="utf-8") as f:
            excluded_content = f.read()
        for designation in EXCLUDED_DESIGNATIONS:
            if designation not in excluded_content:
                errors.append(f"EXCLUDED.md missing entry for: {designation}")
                print(f"  FAIL: {designation} not documented in EXCLUDED.md")
            else:
                print(f"  OK: {designation} documented in EXCLUDED.md")
    else:
        errors.append("EXCLUDED.md not found at " + EXCLUDED_FILE)
        print("  FAIL: EXCLUDED.md not found")
    print()

    # Summary
    print("=" * 60)
    if errors:
        print(f"RESULT: FAIL ({len(errors)} errors)")
        print()
        for e in errors:
            print(f"  ERROR: {e}")
        sys.exit(1)
    else:
        print("RESULT: PASS (all checks passed)")
        print(f"  Manifests validated: {len(manifest_files)}")
        print(f"  PDFs verified: {len(all_pdfs)}")
        print(f"  Excluded documents: {len(EXCLUDED_DESIGNATIONS)}")
        sys.exit(0)


if __name__ == "__main__":
    main()
