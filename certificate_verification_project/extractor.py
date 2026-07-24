import shutil
from pathlib import Path

from pypdf import PdfReader, PdfWriter

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def extract_certificates(source_path: Path, output_dir: Path) -> list[Path]:
    """Save one file per certificate: each PDF page, or a single image file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = source_path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf_pages(source_path, output_dir)
    if suffix in IMAGE_EXTENSIONS:
        return _extract_single_image(source_path, output_dir)
    raise ValueError(f"Unsupported file type: {suffix}")


def _extract_pdf_pages(pdf_path: Path, output_dir: Path) -> list[Path]:
    reader = PdfReader(str(pdf_path))
    if not reader.pages:
        raise ValueError("PDF has no pages.")

    stem = pdf_path.stem
    extracted: list[Path] = []

    for index, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        out_path = output_dir / f"{stem}_certificate_{index:04d}.pdf"
        with out_path.open("wb") as out_file:
            writer.write(out_file)
        extracted.append(out_path)

    return extracted


def _extract_single_image(image_path: Path, output_dir: Path) -> list[Path]:
    stem = image_path.stem
    out_path = output_dir / f"{stem}_certificate_0001{image_path.suffix.lower()}"
    shutil.copy2(image_path, out_path)
    return [out_path]
