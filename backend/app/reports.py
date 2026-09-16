"""Compliance report generation: shared template data → PDF (WeasyPrint) + DOCX."""

from __future__ import annotations

import base64
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings
from app.schema import ScanRecord, ScanReviewStatus

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def template_context(record: ScanRecord) -> dict:
    pending = record.review_status != ScanReviewStatus.approved
    image_data_uri = None
    if record.product and record.product.image_path:
        raw_path = record.product.image_path
        candidates = [
            Path(raw_path),
            Path("captures") / raw_path,
            Path("captures") / raw_path.replace("scans/", ""),
            Path("captures") / record.scan_id / "evidence.jpg",
        ]
        # Also check captures/{scan_id} folder for any image
        scan_dir = Path("captures") / record.scan_id
        if scan_dir.is_dir():
            for f in scan_dir.iterdir():
                if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                    candidates.append(f)

        for img_p in candidates:
            if img_p.is_file():
                try:
                    raw_bytes = img_p.read_bytes()
                    mime = "image/png" if img_p.suffix.lower() == ".png" else "image/jpeg"
                    image_data_uri = f"data:{mime};base64,{base64.b64encode(raw_bytes).decode('ascii')}"
                    break
                except Exception:
                    pass

    return {
        "record": record,
        "image_data_uri": image_data_uri,
        "show_disclaimer": pending,
        "disclaimer": (
            "DRAFT — Not officer-approved. This report is provisional and must not "
            "be treated as a final Legal Metrology enforcement document."
        ),
    }


def render_html(record: ScanRecord) -> str:
    return _env().get_template("report.html.j2").render(**template_context(record))


_WEASYPRINT_AVAILABLE: bool | None = None


def _is_weasyprint_available() -> bool:
    global _WEASYPRINT_AVAILABLE
    if _WEASYPRINT_AVAILABLE is not None:
        return _WEASYPRINT_AVAILABLE
    try:
        import os
        import sys

        with open(os.devnull, "w") as devnull:
            old_stderr = sys.stderr
            sys.stderr = devnull
            try:
                from weasyprint import HTML  # noqa: F401

                _WEASYPRINT_AVAILABLE = True
            finally:
                sys.stderr = old_stderr
    except Exception:
        _WEASYPRINT_AVAILABLE = False
    return _WEASYPRINT_AVAILABLE


def write_pdf(record: ScanRecord, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    html = render_html(record)
    if _is_weasyprint_available():
        try:
            from weasyprint import HTML

            HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(str(dest))
            return dest
        except Exception:
            pass
    # Environments without WeasyPrint system libs still get a retrievable artifact.
    dest.write_text(html, encoding="utf-8")
    return dest.with_suffix(".html")


def write_docx(record: ScanRecord, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ctx = template_context(record)
    doc = Document()
    doc.add_heading("Legal Metrology Compliance Report", level=1)
    doc.add_paragraph(f"Report No: {record.report_no}  |  Version: {record.report_version}")
    doc.add_paragraph(f"Scan ID: {record.scan_id}")
    doc.add_paragraph(f"Hash: {record.report_hash}")
    if record.previous_report_hash:
        doc.add_paragraph(f"Previous hash: {record.previous_report_hash}")
    doc.add_paragraph(
        f"Scanned: {record.date_scanned.isoformat()}  |  "
        f"GPS: {record.gps.lat}, {record.gps.lng}"
    )
    doc.add_paragraph(
        f"Inspector: {record.inspector_id}  |  District: {record.district_id}  |  "
        f"State: {record.state_id}"
    )
    doc.add_heading("Product", level=2)
    doc.add_paragraph(
        f"{record.product.name} — {record.product.manufacturer} ({record.product.category})"
    )
    doc.add_heading("Declarations", level=2)
    table = doc.add_table(rows=1, cols=4)
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = "Field", "Value", "Status", "Remark"
    for d in record.declarations:
        row = table.add_row().cells
        row[0].text = d.field
        row[1].text = d.detected_value or ""
        row[2].text = d.status.value
        row[3].text = d.remark or ""
    if record.ingredients:
        doc.add_heading("Ingredients", level=2)
        for ing in record.ingredients:
            doc.add_paragraph(f"{ing.name}" + (f" — {ing.quantity}" if ing.quantity else ""))
    doc.add_heading("Verdict", level=2)
    doc.add_paragraph(f"Overall: {record.overall_verdict.value}")
    doc.add_paragraph(record.remarks_summary)
    doc.add_paragraph(f"QR: {record.qr_payload}")
    if ctx["show_disclaimer"]:
        p = doc.add_paragraph(ctx["disclaimer"])
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.save(str(dest))
    return dest


def generate_report_files(record: ScanRecord) -> tuple[Path, Path]:
    settings = get_settings()
    base = Path(settings.report_storage_dir) / record.scan_id / f"v{record.report_version}"
    pdf_path = write_pdf(record, base / "report.pdf")
    docx_path = write_docx(record, base / "report.docx")
    return pdf_path, docx_path
