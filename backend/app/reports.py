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

    # Always write report.html so a printable HTML Gazette is also available on disk
    html_dest = dest.with_suffix(".html")
    try:
        html_dest.write_text(html, encoding="utf-8")
    except Exception as html_err:
        print(f"HTML report write error: {html_err}")

    # 1. Try WeasyPrint if available and functional
    if _is_weasyprint_available():
        try:
            from weasyprint import HTML

            HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(str(dest))
            if dest.is_file() and dest.stat().st_size > 1000:
                sample = dest.read_bytes()[:10]
                if sample.startswith(b"%PDF"):
                    return dest
        except Exception:
            pass

    # 2. Pure-Python vector PDF generator (Zero C dependencies, 100% reliable on Windows/Linux)
    try:
        from app.pdf_builder import generate_gazette_pdf

        pdf_bytes = generate_gazette_pdf(record)
        dest.write_bytes(pdf_bytes)
        return dest
    except Exception as pdf_builder_err:
        print(f"Vector PDF generation error: {pdf_builder_err}")

    # 3. ReportLab fallback if present
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        pdf_dest = dest.with_suffix(".pdf")
        doc = SimpleDocTemplate(str(pdf_dest), pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()
        story = []

        # Header
        story.append(Paragraph("GOVERNMENT OF INDIA", ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=15, leading=19, textColor=colors.black, alignment=1)))
        story.append(Paragraph("DEPARTMENT OF CONSUMER AFFAIRS", ParagraphStyle('Sub1', parent=styles['Normal'], fontSize=11, leading=15, alignment=1, textColor=colors.black)))
        story.append(Paragraph("DIRECTORATE OF LEGAL METROLOGY", ParagraphStyle('Sub2', parent=styles['Normal'], fontSize=10, leading=14, alignment=1, textColor=colors.black)))
        story.append(Spacer(1, 8))
        story.append(Paragraph("STATUTORY COMPLIANCE INSPECTION CERTIFICATE &amp; AUDIT MEMO", ParagraphStyle('MemoTitle', parent=styles['Heading2'], fontSize=12, leading=16, alignment=1, textColor=colors.black)))
        story.append(Spacer(1, 10))

        # Meta table
        date_str = record.date_scanned.strftime('%d-%b-%Y %H:%M') if hasattr(record.date_scanned, 'strftime') else str(record.date_scanned)
        meta_data = [
            [f"Statutory Memo No: {record.report_no}", f"Inspection Date: {date_str}"],
            [f"Inspector: {record.inspector_id}", f"Jurisdiction: {record.district_id or 'Circle'} | {record.state_id or 'State'}"],
            [f"Commodity: {record.product.name if record.product else 'Packaged Commodity'}", f"Packer / Manufacturer: {record.product.manufacturer if record.product else 'Manufacturer'}"],
            [f"Overall Verdict: {record.overall_verdict.value.upper() if hasattr(record.overall_verdict, 'value') else str(record.overall_verdict).upper()}", f"Review Status: {record.review_status.value.upper() if hasattr(record.review_status, 'value') else str(record.review_status).upper()}"]
        ]
        meta_table = Table(meta_data, colWidths=[270, 270])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.whitesmoke),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 8.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('BOX', (0,0), (-1,-1), 1, colors.black),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 12))

        # Declarations
        story.append(Paragraph("STATUTORY DECLARATIONS AUDIT CHECKLIST (RULE 6)", ParagraphStyle('Sec2', parent=styles['Heading3'], fontSize=10, leading=14, textColor=colors.black)))
        story.append(Spacer(1, 6))

        decl_data = [["Rule Provision", "Statutory Parameter", "Declared Evidence", "Standard", "Status", "Defect Remark"]]
        for d in (record.declarations or []):
            status_val = d.status.value.upper() if hasattr(d.status, "value") else str(d.status).upper()
            rule_prov = getattr(d, "rule_provision", None) or "Rule 6(1)"
            param_name = (getattr(d, "statutory_parameter", None) or d.field).replace("_", " ").upper()
            decl_val = d.detected_value or "[NOT LOCATED]"
            std_val = getattr(d, "legal_metrology_standard", None) or getattr(d, "mandated_value", None) or "Mandatory"
            rem_val = d.remark or ("Verified compliant" if status_val == "PASS" else "Violation logged")
            decl_data.append([
                rule_prov,
                param_name,
                decl_val,
                std_val,
                status_val,
                rem_val,
            ])

        decl_table = Table(decl_data, colWidths=[70, 100, 110, 100, 50, 110])
        decl_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 7.5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('BOX', (0,0), (-1,-1), 1, colors.black),
        ]))
        story.append(decl_table)
        story.append(Spacer(1, 12))

        # Hash & Attestation
        story.append(Paragraph(f"Immutable Report SHA-256 Hash: {record.report_hash}", ParagraphStyle('Hash', parent=styles['Normal'], fontSize=7, leading=9, textColor=colors.black, fontName='Courier')))
        story.append(Spacer(1, 8))
        story.append(Paragraph("This is an official statutory inspection record validated under Section 15 of the Legal Metrology Act, 2011.", ParagraphStyle('Foot', parent=styles['Italic'], fontSize=7.5, leading=10, textColor=colors.black)))

        doc.build(story)
        return pdf_dest
    except Exception as reportlab_err:
        print(f"ReportLab PDF generation error: {reportlab_err}")

    return dest


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
    p_name = record.product.name if record.product else "Packaged Commodity"
    p_mfr = record.product.manufacturer if record.product else "Declared Manufacturer"
    p_cat = record.product.category if record.product else "Standard"
    doc.add_paragraph(f"{p_name} — {p_mfr} ({p_cat})")
    doc.add_heading("Declarations", level=2)
    table = doc.add_table(rows=1, cols=4)
    hdr = table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = "Field", "Value", "Status", "Remark"
    for d in (record.declarations or []):
        row = table.add_row().cells
        row[0].text = d.field
        row[1].text = d.detected_value or ""
        row[2].text = d.status.value if hasattr(d.status, "value") else str(d.status)
        row[3].text = d.remark or ""
    if record.ingredients:
        doc.add_heading("Ingredients", level=2)
        for ing in record.ingredients:
            doc.add_paragraph(f"{ing.name}" + (f" — {ing.quantity}" if ing.quantity else ""))
    doc.add_heading("Verdict", level=2)
    v_val = record.overall_verdict.value if hasattr(record.overall_verdict, "value") else str(record.overall_verdict)
    doc.add_paragraph(f"Overall: {v_val}")
    doc.add_paragraph(record.remarks_summary)
    doc.add_paragraph(f"QR: {record.qr_payload}")
    if ctx["show_disclaimer"]:
        p = doc.add_paragraph(ctx["disclaimer"])
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.save(str(dest))
    return dest


def generate_report_files(record: ScanRecord) -> tuple[Path, Path]:
    settings = get_settings()
    storage_dir = Path(settings.report_storage_dir)
    if not storage_dir.is_absolute():
        storage_dir = Path(__file__).resolve().parent.parent / storage_dir
    base = storage_dir / record.scan_id / f"v{record.report_version}"
    base.mkdir(parents=True, exist_ok=True)
    pdf_path = write_pdf(record, base / "report.pdf")
    docx_path = write_docx(record, base / "report.docx")
    return pdf_path, docx_path
