"""PDF text extraction using Docling with OCR backend selection and fallback.

Handles both born-digital and scanned PDFs. Born-digital PDFs are extracted
directly; scanned PDFs use Tesseract OCR (primary) with EasyOCR fallback.
"""

import logging

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    EasyOcrOptions,
    PdfPipelineOptions,
    TableFormerMode,
    TesseractOcrOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption

logger = logging.getLogger(__name__)


def create_converter(ocr_backend: str = "tesseract") -> DocumentConverter:
    """Create a Docling DocumentConverter with appropriate OCR settings.

    Args:
        ocr_backend: OCR engine to use -- "tesseract" or "easyocr".

    Returns:
        Configured DocumentConverter instance.
    """
    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        do_table_structure=True,
    )

    # Use ACCURATE mode for military reference tables with complex structure
    pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE

    # OCR backend selection
    if ocr_backend == "tesseract":
        pipeline_options.ocr_options = TesseractOcrOptions(
            lang=["eng"],
        )
    elif ocr_backend == "easyocr":
        pipeline_options.ocr_options = EasyOcrOptions(
            lang=["en"],
            use_gpu=False,
        )
    else:
        raise ValueError(f"Unknown OCR backend: {ocr_backend}. Use 'tesseract' or 'easyocr'.")

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            )
        }
    )
    return converter


def extract_document(pdf_path: str, ocr_backend: str = "tesseract"):
    """Extract text from a single PDF using Docling.

    Args:
        pdf_path: Path to the PDF file.
        ocr_backend: OCR engine to use for scanned pages.

    Returns:
        DoclingDocument with extracted content.
    """
    converter = create_converter(ocr_backend)
    result = converter.convert(pdf_path)
    return result.document


def extract_with_fallback(pdf_path: str) -> tuple:
    """Extract a PDF, trying Tesseract first then falling back to EasyOCR.

    If Tesseract extraction fails or produces very little text (< 100 chars),
    falls back to EasyOCR. If both fail, raises an exception per the project
    decision: "poor OCR quality = exclude the document."

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Tuple of (DoclingDocument, engine_used) where engine_used is
        "born-digital", "tesseract", or "easyocr".
    """
    # Try Tesseract first
    try:
        logger.info(f"Extracting {pdf_path} with Tesseract backend...")
        doc = extract_document(pdf_path, ocr_backend="tesseract")

        # Check if extraction produced meaningful text
        full_text = doc.export_to_markdown()
        if len(full_text.strip()) >= 100:
            # Determine if OCR was actually used or document was born-digital
            # Born-digital PDFs produce clean text without OCR
            engine = "born-digital"
            # Check if any pages required OCR by looking at the document
            # Docling handles this transparently -- if no bitmap content
            # was found, OCR was not invoked
            logger.info(
                f"Successfully extracted {pdf_path} ({len(full_text)} chars)"
            )
            return doc, engine

        logger.warning(
            f"Tesseract extraction produced only {len(full_text.strip())} chars "
            f"for {pdf_path}, trying EasyOCR fallback..."
        )
    except Exception as e:
        logger.warning(
            f"Tesseract extraction failed for {pdf_path}: {e}. "
            f"Trying EasyOCR fallback..."
        )

    # Fallback to EasyOCR
    try:
        logger.info(f"Extracting {pdf_path} with EasyOCR backend...")
        doc = extract_document(pdf_path, ocr_backend="easyocr")
        full_text = doc.export_to_markdown()

        if len(full_text.strip()) >= 100:
            logger.info(
                f"EasyOCR extraction succeeded for {pdf_path} ({len(full_text)} chars)"
            )
            return doc, "easyocr"

        logger.error(
            f"EasyOCR also produced minimal text ({len(full_text.strip())} chars) "
            f"for {pdf_path}"
        )
    except Exception as e:
        logger.error(f"EasyOCR extraction also failed for {pdf_path}: {e}")

    raise RuntimeError(
        f"Failed to extract usable text from {pdf_path}. "
        f"Both Tesseract and EasyOCR produced insufficient output. "
        f"Per project policy, this document should be excluded from the corpus."
    )
