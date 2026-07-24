from pathlib import Path
from typing import Iterator

import fitz
import pytesseract
from PIL import Image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
PDF_EXTENSION = ".pdf"
OCR_DPI = 200


def is_image_path(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def is_pdf_path(path: Path) -> bool:
    return path.suffix.lower() == PDF_EXTENSION


def extract_text_from_pil(image: Image.Image) -> str:
    """Run Tesseract OCR on a PIL image and return recognized text."""
    rgb = image.convert("RGB")
    return pytesseract.image_to_string(rgb).strip()


def extract_text_from_image(image_path: Path) -> str:
    with Image.open(image_path) as image:
        return extract_text_from_pil(image)


def page_to_image(page: fitz.Page) -> Image.Image:
    pixmap = page.get_pixmap(dpi=OCR_DPI)
    return Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)


def get_certificate_images(
    original_path: Path,
    extracted_paths: list[Path],
    relative_files: list[str],
) -> Iterator[tuple[str, Path, Image.Image]]:
    """Yield (relative_path, disk_path, PIL image) for each certificate."""
    if is_image_path(original_path):
        image = Image.open(extracted_paths[0])
        yield relative_files[0], extracted_paths[0], image
        return

    if is_pdf_path(original_path):
        with fitz.open(original_path) as document:
            for rel_file, disk_path, page in zip(
                relative_files, extracted_paths, document
            ):
                yield rel_file, disk_path, page_to_image(page)


def extract_text_from_pdf(pdf_path: Path) -> list[str]:
    """Render each PDF page to an image, then run OCR (one text block per page)."""
    texts: list[str] = []
    with fitz.open(pdf_path) as document:
        for page in document:
            image = page_to_image(page)
            try:
                texts.append(extract_text_from_pil(image))
            finally:
                image.close()
    return texts
