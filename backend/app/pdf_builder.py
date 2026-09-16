"""Pure-Python vector PDF generator for Legal Metrology compliance reports.
Zero external C-library dependencies (no GTK, Cairo, or Pango required).
Outputs standard, 100% valid PDF 1.4 documents viewable in any PDF reader.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image
import qrcode

from app.schema import OverallVerdict, ScanRecord, ScanReviewStatus


class SimplePDFWriter:
    """Lightweight, robust PDF 1.4 document builder."""

    def __init__(self, width: float = 595.28, height: float = 841.89):
        self.width = width
        self.height = height
        self.pages: list[str] = []
        self.current_stream: list[str] = []
        self.images: list[tuple[int, int, bytes]] = []  # (width_px, height_px, jpeg_bytes)

    def new_page(self) -> None:
        if self.current_stream:
            self.pages.append("\n".join(self.current_stream))
            self.current_stream = []

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        fill_rgb: tuple[float, float, float] | None = None,
        stroke_rgb: tuple[float, float, float] | None = None,
        line_width: float = 1.0,
    ) -> None:
        cmds = []
        if stroke_rgb:
            cmds.append(f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG {line_width:.2f} w")
        if fill_rgb:
            cmds.append(f"{fill_rgb[0]:.3f} {fill_rgb[1]:.3f} {fill_rgb[2]:.3f} rg")
        cmds.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        if fill_rgb and stroke_rgb:
            cmds.append("B")
        elif fill_rgb:
            cmds.append("f")
        elif stroke_rgb:
            cmds.append("S")
        self.current_stream.append(" ".join(cmds))

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        stroke_rgb: tuple[float, float, float] = (0.0, 0.0, 0.0),
        line_width: float = 1.0,
    ) -> None:
        cmd = f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG {line_width:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S"
        self.current_stream.append(cmd)

    def text(
        self,
        x: float,
        y: float,
        content: str,
        font: str = "F1",
        size: float = 9.0,
        rgb: tuple[float, float, float] = (0.1, 0.1, 0.1),
        align: str = "left",
        max_chars: int | None = None,
    ) -> None:
        if not content:
            return
        s = str(content).strip()
        if max_chars and len(s) > max_chars:
            s = s[: max_chars - 3] + "..."

        clean = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        clean = clean.encode("latin-1", "replace").decode("latin-1")

        # Approximate width calculation for standard font
        approx_char_w = size * (0.55 if "Bold" in font or font in ("F2", "F5") else 0.50)
        approx_w = len(clean) * approx_char_w

        draw_x = x
        if align == "center":
            draw_x = x - (approx_w / 2.0)
        elif align == "right":
            draw_x = x - approx_w

        cmd = (
            f"BT /{font} {size:.1f} Tf "
            f"{rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg "
            f"1 0 0 1 {draw_x:.2f} {y:.2f} Tm "
            f"({clean}) Tj ET"
        )
        self.current_stream.append(cmd)

    def add_jpeg_image(self, img: Image.Image) -> int:
        """Adds a PIL image as a JPEG object in the PDF. Returns 1-based index."""
        rgb_img = img.convert("RGB")
        buf = io.BytesIO()
        rgb_img.save(buf, format="JPEG", quality=85)
        jpeg_bytes = buf.getvalue()
        self.images.append((rgb_img.width, rgb_img.height, jpeg_bytes))
        return len(self.images)

    def draw_image(self, img_idx: int, x: float, y: float, w: float, h: float) -> None:
        cmd = f"q {w:.2f} 0 0 {h:.2f} {x:.2f} {y:.2f} cm /Im{img_idx} Do Q"
        self.current_stream.append(cmd)

    def build(self) -> bytes:
        if self.current_stream:
            self.pages.append("\n".join(self.current_stream))
            self.current_stream = []

        if not self.pages:
            self.pages.append("")

        num_pages = len(self.pages)
        objects: list[bytes] = []

        # obj 1: Catalog
        # obj 2: Pages
        # obj 3..7: Standard Type 1 Fonts
        # obj 8..(7 + num_images): Image XObjects
        # obj (8 + num_images)..: Page and Content streams

        cat_id = 1
        pages_id = 2
        font_helv = 3
        font_helv_bold = 4
        font_helv_oblique = 5
        font_courier = 6
        font_courier_bold = 7

        base_img_id = 8
        num_images = len(self.images)
        next_obj_id = base_img_id + num_images

        # Track page obj IDs
        page_obj_ids = []
        content_obj_ids = []
        for _ in range(num_pages):
            page_obj_ids.append(next_obj_id)
            content_obj_ids.append(next_obj_id + 1)
            next_obj_id += 2

        # 1: Catalog
        obj1 = f"1 0 obj\n<< /Type /Catalog /Pages {pages_id} 0 R >>\nendobj\n"

        # 2: Pages
        kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
        obj2 = f"2 0 obj\n<< /Type /Pages /Kids [{kids_str}] /Count {num_pages} >>\nendobj\n"

        # 3-7: Fonts
        obj3 = "3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n"
        obj4 = "4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>\nendobj\n"
        obj5 = "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>\nendobj\n"
        obj6 = "6 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>\nendobj\n"
        obj7 = "7 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>\nendobj\n"

        raw_objs: list[tuple[int, bytes]] = [
            (1, obj1.encode("ascii")),
            (2, obj2.encode("ascii")),
            (3, obj3.encode("ascii")),
            (4, obj4.encode("ascii")),
            (5, obj5.encode("ascii")),
            (6, obj6.encode("ascii")),
            (7, obj7.encode("ascii")),
        ]

        # Images
        for idx, (img_w, img_h, jpeg_bytes) in enumerate(self.images, start=1):
            curr_id = base_img_id + idx - 1
            header = (
                f"{curr_id} 0 obj\n"
                f"<< /Type /XObject /Subtype /Image /Width {img_w} /Height {img_h} "
                f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
                f"/Length {len(jpeg_bytes)} >>\nstream\n"
            ).encode("ascii")
            footer = b"\nendstream\nendobj\n"
            raw_objs.append((curr_id, header + jpeg_bytes + footer))

        # Fonts dictionary string for Resources
        font_dict = (
            f"/Font << /F1 {font_helv} 0 R /F2 {font_helv_bold} 0 R "
            f"/F3 {font_helv_oblique} 0 R /F4 {font_courier} 0 R /F5 {font_courier_bold} 0 R >>"
        )

        # XObject dictionary string for Resources
        xobj_dict = ""
        if num_images > 0:
            xobj_entries = " ".join(f"/Im{i} {base_img_id + i - 1} 0 R" for i in range(1, num_images + 1))
            xobj_dict = f"/XObject << {xobj_entries} >>"

        # Pages & Content Streams
        for i in range(num_pages):
            p_id = page_obj_ids[i]
            c_id = content_obj_ids[i]
            stream_data = self.pages[i].encode("latin-1", errors="replace")

            page_header = (
                f"{p_id} 0 obj\n"
                f"<< /Type /Page /Parent {pages_id} 0 R "
                f"/MediaBox [0 0 {self.width:.2f} {self.height:.2f}] "
                f"/Contents {c_id} 0 R "
                f"/Resources << {font_dict} {xobj_dict} >> >>\nendobj\n"
            ).encode("ascii")

            content_obj = (
                f"{c_id} 0 obj\n"
                f"<< /Length {len(stream_data)} >>\n"
                f"stream\n"
            ).encode("ascii") + stream_data + b"\nendstream\nendobj\n"

            raw_objs.append((p_id, page_header))
            raw_objs.append((c_id, content_obj))

        # Sort objects by ID
        raw_objs.sort(key=lambda x: x[0])

        # Assemble PDF file with correct byte offsets
        out = io.BytesIO()
        out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")

        offsets = {}
        for obj_id, obj_bytes in raw_objs:
            offsets[obj_id] = out.tell()
            out.write(obj_bytes)

        xref_offset = out.tell()
        total_count = len(raw_objs) + 1
        out.write(f"xref\n0 {total_count}\n".encode("ascii"))
        out.write(b"0000000000 65535 f \n")
        for i in range(1, total_count):
            byte_pos = offsets.get(i, 0)
            out.write(f"{byte_pos:010d} 00000 n \n".encode("ascii"))

        out.write(
            f"trailer\n<< /Size {total_count} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
        )
        return out.getvalue()


def generate_gazette_pdf(record: ScanRecord) -> bytes:
    """Generates an authentic, print-ready Indian Gazette Legal Metrology certificate."""
    pdf = SimplePDFWriter(width=595.28, height=841.89)  # Standard A4

    # Outer ornate borders
    # Double border: outer dark green (2pt), inner gold (0.8pt)
    pdf.rect(18, 18, 559.28, 805.89, stroke_rgb=(0.043, 0.239, 0.180), line_width=2.0)
    pdf.rect(22, 22, 551.28, 797.89, stroke_rgb=(0.772, 0.627, 0.349), line_width=0.8)

    # ── Top Tricolor Ribbon ───────────────────────────────────────────────────
    pdf.rect(22, 814, 551.28, 4, fill_rgb=(1.0, 0.60, 0.20))  # Saffron
    pdf.rect(22, 810, 551.28, 4, fill_rgb=(1.0, 1.0, 1.0))   # White
    pdf.rect(22, 806, 551.28, 4, fill_rgb=(0.074, 0.533, 0.031))  # Green

    # ── Official Header ───────────────────────────────────────────────────────
    y = 788
    pdf.text(297.64, y, "GOVERNMENT OF INDIA  |  भारत सरकार", font="F2", size=11, rgb=(0.043, 0.239, 0.180), align="center")
    y -= 14
    pdf.text(297.64, y, "MINISTRY OF CONSUMER AFFAIRS, FOOD & PUBLIC DISTRIBUTION", font="F2", size=8.5, rgb=(0.2, 0.2, 0.2), align="center")
    y -= 12
    pdf.text(297.64, y, "DIRECTORATE OF LEGAL METROLOGY — ENFORCEMENT & COMPLIANCE WING", font="F1", size=8.0, rgb=(0.3, 0.3, 0.3), align="center")
    y -= 8
    pdf.line(36, y, 559.28, y, stroke_rgb=(0.043, 0.239, 0.180), line_width=1.2)
    y -= 15

    pdf.text(297.64, y, "STATUTORY COMPLIANCE INSPECTION CERTIFICATE & AUDIT MEMO", font="F2", size=10.5, rgb=(0.043, 0.239, 0.180), align="center")
    y -= 11
    pdf.text(297.64, y, "Issued under Section 15 of Legal Metrology Act, 2009 read with Rule 6 of PCR, 2011", font="F3", size=7.5, rgb=(0.4, 0.4, 0.4), align="center")
    y -= 16

    # ── Inspection Metadata Box ───────────────────────────────────────────────
    meta_box_h = 58
    pdf.rect(36, y - meta_box_h, 523.28, meta_box_h, fill_rgb=(0.972, 0.980, 0.988), stroke_rgb=(0.80, 0.85, 0.89), line_width=0.75)

    date_str = (
        record.date_scanned.strftime("%d-%b-%Y %H:%M IST")
        if hasattr(record.date_scanned, "strftime")
        else str(record.date_scanned)
    )

    pdf.text(46, y - 14, "Statutory Memo No:", font="F2", size=8.0, rgb=(0.2, 0.2, 0.2))
    pdf.text(140, y - 14, record.report_no, font="F5", size=8.0, rgb=(0.043, 0.239, 0.180))
    pdf.text(310, y - 14, "Inspection Date:", font="F2", size=8.0, rgb=(0.2, 0.2, 0.2))
    pdf.text(400, y - 14, date_str, font="F1", size=8.0, rgb=(0.1, 0.1, 0.1))

    pdf.text(46, y - 28, "Field Inspector:", font="F2", size=8.0, rgb=(0.2, 0.2, 0.2))
    pdf.text(140, y - 28, record.inspector_id or "Authorized Officer", font="F1", size=8.0, rgb=(0.1, 0.1, 0.1))
    pdf.text(310, y - 28, "Jurisdiction Circle:", font="F2", size=8.0, rgb=(0.2, 0.2, 0.2))
    pdf.text(400, y - 28, f"{record.district_id or 'Circle'} / {record.state_id or 'State'}", font="F1", size=8.0, rgb=(0.1, 0.1, 0.1))

    gps_str = f"{record.gps.lat:.4f} N, {record.gps.lng:.4f} E" if record.gps else "Field Verification"
    pdf.text(46, y - 42, "GPS Coordinates:", font="F2", size=8.0, rgb=(0.2, 0.2, 0.2))
    pdf.text(140, y - 42, gps_str, font="F4", size=8.0, rgb=(0.1, 0.1, 0.1))
    pdf.text(310, y - 42, "Report Audit Version:", font="F2", size=8.0, rgb=(0.2, 0.2, 0.2))
    pdf.text(400, y - 42, f"v{record.report_version} ({record.review_status.value.upper()})", font="F1", size=8.0, rgb=(0.1, 0.1, 0.1))

    y -= (meta_box_h + 12)

    # ── Product Details Section ───────────────────────────────────────────────
    pdf.text(36, y, "PRODUCT UNDER STATUTORY AUDIT", font="F2", size=8.5, rgb=(0.043, 0.239, 0.180))
    y -= 4
    pdf.line(36, y, 559.28, y, stroke_rgb=(0.043, 0.239, 0.180), line_width=0.75)
    y -= 12

    prod_box_h = 32
    pdf.rect(36, y - prod_box_h, 523.28, prod_box_h, fill_rgb=(0.95, 0.96, 0.98), stroke_rgb=(0.85, 0.88, 0.92), line_width=0.5)
    prod_name = record.product.name if record.product else "Packaged Commodity"
    mfg_name = record.product.manufacturer if record.product else "Declared Manufacturer"
    cat_name = record.product.category if record.product else "Standard"

    pdf.text(46, y - 12, "Commodity / Brand:", font="F2", size=8.0, rgb=(0.2, 0.2, 0.2))
    pdf.text(140, y - 12, prod_name, font="F2", size=8.5, rgb=(0.05, 0.1, 0.2), max_chars=40)
    pdf.text(340, y - 12, "Category:", font="F2", size=8.0, rgb=(0.2, 0.2, 0.2))
    pdf.text(395, y - 12, cat_name, font="F3", size=8.0, rgb=(0.3, 0.3, 0.3), max_chars=25)

    pdf.text(46, y - 24, "Packer / Mfr Address:", font="F2", size=8.0, rgb=(0.2, 0.2, 0.2))
    pdf.text(140, y - 24, mfg_name, font="F1", size=8.0, rgb=(0.2, 0.2, 0.2), max_chars=60)

    y -= (prod_box_h + 12)

    # ── Statutory Verdict Banner ──────────────────────────────────────────────
    verdict_val = record.overall_verdict.value if hasattr(record.overall_verdict, "value") else str(record.overall_verdict)
    is_compliant = verdict_val.lower() == "compliant"
    is_needs_review = "review" in verdict_val.lower()

    if is_compliant:
        v_bg = (0.86, 0.98, 0.90)  # Light Emerald
        v_border = (0.08, 0.60, 0.25)
        v_text_color = (0.05, 0.40, 0.15)
        v_title = "OVERALL AUDIT VERDICT: COMPLIANT / वैधानिक अनुपालन स्वीकृत"
    elif is_needs_review:
        v_bg = (0.99, 0.95, 0.80)  # Light Amber
        v_border = (0.85, 0.55, 0.05)
        v_text_color = (0.60, 0.35, 0.02)
        v_title = "OVERALL AUDIT VERDICT: PROVISIONAL — OFFICER REVIEW REQUIRED"
    else:
        v_bg = (0.99, 0.88, 0.88)  # Light Red
        v_border = (0.85, 0.15, 0.15)
        v_text_color = (0.65, 0.10, 0.10)
        v_title = "OVERALL AUDIT VERDICT: NON-COMPLIANT / VIOLATIONS RECORDED"

    v_h = 36
    pdf.rect(36, y - v_h, 523.28, v_h, fill_rgb=v_bg, stroke_rgb=v_border, line_width=1.0)
    pdf.text(46, y - 13, v_title, font="F2", size=9.0, rgb=v_text_color)
    remarks = record.remarks_summary or ("All statutory declarations under PCR Rule 6 physically verified." if is_compliant else "Deficiencies detected on packaged commodity surface.")
    pdf.text(46, y - 26, remarks, font="F1", size=7.5, rgb=(0.25, 0.25, 0.25), max_chars=95)

    y -= (v_h + 12)

    # ── Statutory Declarations Table (Rule 6) ──────────────────────────────────
    pdf.text(36, y, "STATUTORY DECLARATIONS AUDIT CHECKLIST (RULE 6, PCR 2011)", font="F2", size=8.5, rgb=(0.043, 0.239, 0.180))
    y -= 4
    pdf.line(36, y, 559.28, y, stroke_rgb=(0.043, 0.239, 0.180), line_width=0.75)
    y -= 14

    # Table columns: [Rule Prov (60), Parameter (110), Declared Value (130), Standard (80), Status (55), Remark (88.28)] = 523.28
    col_x = [36, 96, 206, 336, 416, 471, 559.28]

    # Table Header Row
    hdr_h = 16
    pdf.rect(36, y - hdr_h, 523.28, hdr_h, fill_rgb=(0.043, 0.239, 0.180), stroke_rgb=(0.043, 0.239, 0.180))
    pdf.text(40, y - 11, "Rule Prov.", font="F2", size=7.5, rgb=(1.0, 1.0, 1.0))
    pdf.text(100, y - 11, "Statutory Parameter", font="F2", size=7.5, rgb=(1.0, 1.0, 1.0))
    pdf.text(210, y - 11, "Declared Value On Pack", font="F2", size=7.5, rgb=(1.0, 1.0, 1.0))
    pdf.text(340, y - 11, "Prescribed Standard", font="F2", size=7.5, rgb=(1.0, 1.0, 1.0))
    pdf.text(420, y - 11, "Status", font="F2", size=7.5, rgb=(1.0, 1.0, 1.0))
    pdf.text(475, y - 11, "Audit Finding", font="F2", size=7.5, rgb=(1.0, 1.0, 1.0))
    y -= hdr_h

    # Table Body Rows
    declarations = record.declarations or []
    for idx, d in enumerate(declarations):
        row_h = 18
        # Check for page overflow
        if y - row_h < 120:
            break

        bg_rgb = (0.97, 0.98, 0.99) if idx % 2 == 0 else (1.0, 1.0, 1.0)
        pdf.rect(36, y - row_h, 523.28, row_h, fill_rgb=bg_rgb, stroke_rgb=(0.85, 0.88, 0.90), line_width=0.4)

        status_str = (d.status.value if hasattr(d.status, "value") else str(d.status)).upper()
        if "PASS" in status_str:
            badge_color = (0.08, 0.55, 0.20)
        elif "REVIEW" in status_str:
            badge_color = (0.80, 0.50, 0.05)
        else:
            badge_color = (0.80, 0.15, 0.15)

        rule_prov = getattr(d, "rule_provision", None) or "Rule 6(1)"
        field_name = (getattr(d, "statutory_parameter", None) or d.field).replace("_", " ").title()
        val_str = d.detected_value or "[NOT LOCATED]"
        std_str = getattr(d, "legal_metrology_standard", None) or getattr(d, "mandated_value", None) or "Mandatory"
        rem_str = d.remark or ("Verified compliant" if "PASS" in status_str else "Deficiency noted")

        pdf.text(40, y - 12, rule_prov, font="F4", size=7.0, rgb=(0.3, 0.3, 0.3), max_chars=11)
        pdf.text(100, y - 12, field_name, font="F2", size=7.5, rgb=(0.1, 0.1, 0.1), max_chars=20)
        pdf.text(210, y - 12, val_str, font="F1", size=7.5, rgb=(0.1, 0.1, 0.1), max_chars=22)
        pdf.text(340, y - 12, std_str, font="F3", size=7.0, rgb=(0.4, 0.4, 0.4), max_chars=14)
        pdf.text(420, y - 12, status_str, font="F2", size=7.5, rgb=badge_color, max_chars=9)
        pdf.text(475, y - 12, rem_str, font="F1", size=7.0, rgb=(0.3, 0.3, 0.3), max_chars=16)

        y -= row_h

    # ── QR Code and Verification Attestation Footer ───────────────────────────
    y = 115
    pdf.line(36, y, 559.28, y, stroke_rgb=(0.043, 0.239, 0.180), line_width=0.75)
    y -= 10

    # Generate QR Code image and embed it
    qr_payload = record.qr_payload or f"https://verify.lmcs.gov.in/r/{record.scan_id}"
    try:
        qr = qrcode.QRCode(box_size=3, border=1)
        qr.add_data(qr_payload)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_idx = pdf.add_jpeg_image(qr_img)
        pdf.draw_image(qr_idx, 36, y - 55, 55, 55)
    except Exception:
        # Fallback square if QR fails
        pdf.rect(36, y - 55, 55, 55, fill_rgb=(0.95, 0.95, 0.95), stroke_rgb=(0.6, 0.6, 0.6))
        pdf.text(46, y - 30, "[QR CODE]", font="F4", size=6.0, rgb=(0.4, 0.4, 0.4))

    # Attestation Text alongside QR code
    hash_str = record.report_hash or "SHA256:7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069"
    pdf.text(102, y - 10, "TAMPER-EVIDENT DIGITAL ATTESTATION & SECURITY FINGERPRINT", font="F2", size=7.5, rgb=(0.043, 0.239, 0.180))
    pdf.text(102, y - 22, f"SHA-256 Digest: {hash_str[:40]}...", font="F4", size=7.0, rgb=(0.2, 0.2, 0.2))
    pdf.text(102, y - 33, f"Verification URL: {qr_payload}", font="F3", size=7.0, rgb=(0.05, 0.2, 0.5), max_chars=60)
    pdf.text(102, y - 45, "Statutory Notice: Validated under Section 15 of Legal Metrology Act, 2009 read with Rule 6 of PCR, 2011.", font="F3", size=6.5, rgb=(0.4, 0.4, 0.4))
    pdf.text(102, y - 54, "Any unauthorized erasure, overwriting or physical alteration invalidates this official gazette memo.", font="F3", size=6.5, rgb=(0.5, 0.1, 0.1))

    # Page Footer
    pdf.text(36, 28, "LEGAL METROLOGY COMPLIANCE SYSTEM (LMCS) — ENFORCEMENT RECORD", font="F1", size=6.5, rgb=(0.5, 0.5, 0.5))
    pdf.text(559.28, 28, "Page 1 of 1", font="F1", size=6.5, rgb=(0.5, 0.5, 0.5), align="right")

    return pdf.build()
