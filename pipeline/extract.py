"""PDF text extraction using Docling with OCR backend selection and fallback.

Handles both born-digital and scanned PDFs. Born-digital PDFs are extracted
directly without OCR. Scanned PDFs use the best available OCR engine with
a fallback chain: tesserocr -> ocrmac (macOS) -> easyocr.

The OCR engine availability is detected at runtime to handle installations
where optional OCR extras are not installed.
"""

import logging
import platform

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableFormerMode,
)
from docling.document_converter import DocumentConverter, PdfFormatOption

logger = logging.getLogger(__name__)

# Detect available OCR backends at import time
_AVAILABLE_OCR_BACKENDS: list[str] = []


def _detect_ocr_backends() -> list[str]:
    """Detect which OCR backends are available on this system."""
    global _AVAILABLE_OCR_BACKENDS
    if _AVAILABLE_OCR_BACKENDS:
        return _AVAILABLE_OCR_BACKENDS

    backends = []

    # Check tesserocr
    try:
        from docling.datamodel.pipeline_options import TesseractOcrOptions
        # Try to actually import tesserocr to verify it works
        import tesserocr  # noqa: F401
        backends.append("tesseract")
    except (ImportError, OSError):
        pass

    # Check ocrmac (macOS native OCR via Apple Vision)
    if platform.system() == "Darwin":
        try:
            from docling.datamodel.pipeline_options import OcrMacOptions  # noqa: F401
            import ocrmac  # noqa: F401
            backends.append("ocrmac")
        except (ImportError, OSError):
            pass

    # Check easyocr
    try:
        from docling.datamodel.pipeline_options import EasyOcrOptions  # noqa: F401
        import easyocr  # noqa: F401
        backends.append("easyocr")
    except (ImportError, OSError):
        pass

    _AVAILABLE_OCR_BACKENDS = backends
    logger.info(f"Available OCR backends: {backends if backends else ['none']}")
    return backends


def _get_ocr_options(backend: str):
    """Get the OCR options object for a given backend.

    Args:
        backend: One of "tesseract", "ocrmac", "easyocr".

    Returns:
        Configured OCR options instance.
    """
    if backend == "tesseract":
        from docling.datamodel.pipeline_options import TesseractOcrOptions
        return TesseractOcrOptions(lang=["eng"])
    elif backend == "ocrmac":
        from docling.datamodel.pipeline_options import OcrMacOptions
        return OcrMacOptions()
    elif backend == "easyocr":
        from docling.datamodel.pipeline_options import EasyOcrOptions
        return EasyOcrOptions(lang=["en"], use_gpu=False)
    else:
        raise ValueError(f"Unknown OCR backend: {backend}")


def create_converter(ocr_backend: str | None = None) -> DocumentConverter:
    """Create a Docling DocumentConverter with appropriate settings.

    Args:
        ocr_backend: OCR engine to use, or None for no OCR (born-digital).

    Returns:
        Configured DocumentConverter instance.
    """
    do_ocr = ocr_backend is not None

    pipeline_options = PdfPipelineOptions(
        do_ocr=do_ocr,
        do_table_structure=True,
    )

    # Use ACCURATE mode for military reference tables with complex structure
    pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE

    # Set OCR options if OCR is enabled
    if do_ocr and ocr_backend:
        pipeline_options.ocr_options = _get_ocr_options(ocr_backend)

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            )
        }
    )
    return converter


def extract_document(pdf_path: str, ocr_backend: str | None = None):
    """Extract text from a single PDF using Docling.

    Args:
        pdf_path: Path to the PDF file.
        ocr_backend: OCR engine to use, or None for no OCR.

    Returns:
        DoclingDocument with extracted content.
    """
    converter = create_converter(ocr_backend)
    result = converter.convert(pdf_path)
    return result.document


def extract_with_fallback(pdf_path: str) -> tuple:
    """Extract a PDF using the best available method.

    Strategy:
    1. Try born-digital extraction (no OCR) first -- majority of Tier 1
       documents are born-digital and this is fast.
    2. If born-digital produces very little text (< 100 chars), the document
       likely needs OCR. Try available OCR backends in order:
       tesseract -> ocrmac (macOS) -> easyocr.
    3. If all methods fail, raise RuntimeError per project policy:
       "poor OCR quality = exclude the document."

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Tuple of (DoclingDocument, engine_used) where engine_used is
        "born-digital", "tesseract", "ocrmac", or "easyocr".
    """
    # Step 1: Try born-digital extraction (no OCR)
    try:
        logger.info(f"Extracting {pdf_path} (born-digital, no OCR)...")
        doc = extract_document(pdf_path, ocr_backend=None)
        full_text = doc.export_to_markdown()

        if len(full_text.strip()) >= 100:
            logger.info(
                f"Born-digital extraction succeeded for {pdf_path} "
                f"({len(full_text)} chars)"
            )
            return doc, "born-digital"

        logger.warning(
            f"Born-digital extraction produced only {len(full_text.strip())} chars "
            f"for {pdf_path}. Document may need OCR."
        )
    except Exception as e:
        logger.warning(f"Born-digital extraction failed for {pdf_path}: {e}")

    # Step 2: Try OCR backends in priority order
    backends = _detect_ocr_backends()
    if not backends:
        logger.warning(
            "No OCR backends available. Install tesserocr, ocrmac, or easyocr "
            "for scanned PDF support."
        )

    for backend in backends:
        try:
            logger.info(f"Trying OCR extraction with {backend} for {pdf_path}...")
            doc = extract_document(pdf_path, ocr_backend=backend)
            full_text = doc.export_to_markdown()

            if len(full_text.strip()) >= 100:
                logger.info(
                    f"{backend} OCR extraction succeeded for {pdf_path} "
                    f"({len(full_text)} chars)"
                )
                return doc, backend

            logger.warning(
                f"{backend} OCR produced only {len(full_text.strip())} chars "
                f"for {pdf_path}"
            )
        except Exception as e:
            logger.warning(f"{backend} OCR failed for {pdf_path}: {e}")

    # Step 3: All methods failed
    tried = ["born-digital"] + backends if backends else ["born-digital"]
    raise RuntimeError(
        f"Failed to extract usable text from {pdf_path}. "
        f"Tried: {', '.join(tried)}. All produced insufficient output. "
        f"Per project policy, this document should be excluded from the corpus."
    )
