import io
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class NumberedCanvas:
    """Canvas that performs two passes to compute total page count."""
    def __init__(self, *args, **kwargs):
        from reportlab.pdfgen import canvas
        self._canvas = canvas.Canvas(*args, **kwargs)
        self._saved_page_states = []

    def __getattr__(self, name):
        return getattr(self._canvas, name)

    def showPage(self):
        self._saved_page_states.append(dict(self._canvas.__dict__))
        self._canvas._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self._canvas.__dict__.update(state)
            self.draw_page_number(num_pages)
            self._canvas.showPage()
        self._canvas.save()

    def draw_page_number(self, page_count):
        self._canvas.saveState()
        self._canvas.setFont("Helvetica", 8)
        self._canvas.setFillColor(colors.HexColor("#64748b"))
        footer_text = f"Page {self._canvas._pageNumber} of {page_count}  •  StockFlow Smart Management System"
        self._canvas.drawRightString(letter[0] - 0.5 * inch, 0.4 * inch, footer_text)
        self._canvas.restoreState()


class ReportPdfGenerator:
    """
    Generates professional PDF reports and period transaction receipts using ReportLab.
    """

    @classmethod
    def generate_transaction_report_pdf(cls, store, period_data, summary, transactions, filters_applied=None, generated_by="System"):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=45
        )

        styles = getSampleStyleSheet()
        normal = styles['Normal']

        title_style = ParagraphStyle(
            'ReportTitle',
            parent=normal,
            fontName='Helvetica-Bold',
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#0f172a'),
        )
        subtitle_style = ParagraphStyle(
            'ReportSubtitle',
            parent=normal,
            fontName='Helvetica',
            fontSize=10,
            leading=13,
            textColor=colors.HexColor('#475569'),
        )
        section_style = ParagraphStyle(
            'SectionTitle',
            parent=normal,
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=15,
            textColor=colors.HexColor('#1e293b'),
            spaceBefore=12,
            spaceAfter=6,
        )
        small_cell = ParagraphStyle(
            'SmallCell',
            parent=normal,
            fontName='Helvetica',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#1e293b'),
        )
        small_cell_bold = ParagraphStyle(
            'SmallCellBold',
            parent=normal,
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#0f172a'),
        )

        story = []

        # 1. Header with Store Identity
        store_name = store.name if store else "StockFlow Supermarket"
        branch_name = store.branch_name if store else "Main Store"
        tax_pin = store.tax_pin if store else ""
        store_address = store.address if store else ""

        header_data = [
            [
                Paragraph(f"<b>{store_name}</b><br/><font size=9 color='#64748b'>{branch_name} • {store_address}</font>", normal),
                Paragraph(f"<font size=8 color='#64748b'><b>TAX REG / PIN:</b> {tax_pin}<br/><b>Generated:</b> {timezone.now().strftime('%d %b %Y %H:%M')}<br/><b>By:</b> {generated_by}</font>", normal)
            ]
        ]
        header_table = Table(header_data, colWidths=[340, 200])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(header_table)
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0f172a'), spaceBefore=8, spaceAfter=10))

        # 2. Document Title & Period
        story.append(Paragraph("INVENTORY TRANSACTION AUDIT REPORT", title_style))
        story.append(Paragraph(f"Reporting Period: <b>{period_data.get('label', 'All Transactions')}</b>", subtitle_style))
        if filters_applied:
            filter_text = " • ".join([f"<b>{k}:</b> {v}" for k, v in filters_applied.items() if v])
            if filter_text:
                story.append(Paragraph(f"<font size=8 color='#64748b'>Filters: {filter_text}</font>", subtitle_style))
        story.append(Spacer(1, 10))

        # 3. Summary KPI Table
        story.append(Paragraph("EXECUTIVE SUMMARY", section_style))
        summary_data = [
            [
                Paragraph("<b>Total Operations</b>", small_cell),
                Paragraph(str(summary.get('total_transactions', 0)), small_cell_bold),
                Paragraph("<b>Stock IN Operations</b>", small_cell),
                Paragraph(f"+{summary.get('stock_in_units', 0):,} units ({summary.get('stock_in_count', 0)} tx)", small_cell_bold),
            ],
            [
                Paragraph("<b>Unique Products</b>", small_cell),
                Paragraph(str(summary.get('unique_products_count', 0)), small_cell_bold),
                Paragraph("<b>Stock OUT Operations</b>", small_cell),
                Paragraph(f"-{summary.get('stock_out_units', 0):,} units ({summary.get('stock_out_count', 0)} tx)", small_cell_bold),
            ],
            [
                Paragraph("<b>Active Operators</b>", small_cell),
                Paragraph(str(summary.get('unique_users_count', 0)), small_cell_bold),
                Paragraph("<b>Audit Adjustments</b>", small_cell),
                Paragraph(f"{summary.get('adjust_count', 0)} ({summary.get('adjust_units', 0):,} units)", small_cell_bold),
            ]
        ]
        sum_table = Table(summary_data, colWidths=[120, 150, 130, 140])
        sum_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(sum_table)
        story.append(Spacer(1, 12))

        # 4. Detailed Transactions Table
        story.append(Paragraph(f"TRANSACTION LOG ({len(transactions)} Records)", section_style))

        tx_rows = [
            [
                Paragraph("<b>Date/Time</b>", small_cell_bold),
                Paragraph("<b>Ref / Receipt</b>", small_cell_bold),
                Paragraph("<b>Product & SKU</b>", small_cell_bold),
                Paragraph("<b>Type</b>", small_cell_bold),
                Paragraph("<b>Qty</b>", small_cell_bold),
                Paragraph("<b>Operator</b>", small_cell_bold),
                Paragraph("<b>Reason</b>", small_cell_bold),
            ]
        ]

        for m in transactions:
            op_name = m.user.username if m.user else "System"
            role = f" ({m.user.get_role_display()})" if m.user else ""
            t_color = "#16a34a" if m.type == 'IN' else ("#dc2626" if m.type == 'OUT' else "#0284c7")
            qty_sign = "+" if m.type == 'IN' else ("-" if m.type == 'OUT' else "")

            tx_rows.append([
                Paragraph(m.created_at.strftime('%d/%m/%y %H:%M'), small_cell),
                Paragraph(m.receipt_number, small_cell),
                Paragraph(f"<b>{m.product.name}</b><br/><font size=7 color='#64748b'>{m.product.sku}</font>", small_cell),
                Paragraph(f"<font color='{t_color}'><b>{m.get_type_display()}</b></font>", small_cell),
                Paragraph(f"<b>{qty_sign}{m.quantity}</b>", small_cell),
                Paragraph(f"{op_name}<font size=7 color='#64748b'>{role}</font>", small_cell),
                Paragraph(m.reason or "—", small_cell),
            ])

        if len(tx_rows) == 1:
            tx_rows.append([
                Paragraph("<i>No transactions recorded for the selected criteria.</i>", small_cell),
                "", "", "", "", "", ""
            ])

        tx_table = Table(tx_rows, colWidths=[70, 75, 125, 60, 40, 85, 85], repeatRows=1)
        tx_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f172a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(tx_table)

        # 5. Sign-off certification block
        story.append(Spacer(1, 16))
        sign_block = [
            [
                Paragraph("<b>Prepared By:</b>", small_cell),
                Paragraph("<b>Store Auditor / Manager:</b>", small_cell),
                Paragraph("<b>Executive Authorization:</b>", small_cell),
            ],
            [
                Paragraph("<br/><br/>_______________________<br/>Signature & Date", small_cell),
                Paragraph("<br/><br/>_______________________<br/>Signature & Date", small_cell),
                Paragraph("<br/><br/>_______________________<br/>Official Store Stamp", small_cell),
            ]
        ]
        sign_table = Table(sign_block, colWidths=[180, 180, 180])
        sign_table.setStyle(TableStyle([
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(KeepTogether([
            HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e1'), spaceBefore=8, spaceAfter=8),
            sign_table
        ]))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()


    @classmethod
    def generate_period_receipt_pdf(cls, store, period_data, summary, transactions, generated_by="Admin"):
        """
        Generates a voucher-style transaction receipt summarizing all operations for the period.
        """
        # We reuse the main transaction report layout formatted specifically as a formal receipt document
        return cls.generate_transaction_report_pdf(
            store=store,
            period_data=period_data,
            summary=summary,
            transactions=transactions,
            filters_applied={'Document Type': 'Official Period Transaction Receipt'},
            generated_by=generated_by
        )
