from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, PageBreak, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

from .schema import BoardMinutes_v1


class PDFGenerator:
    """Generate professional PDF documents from board minutes."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""

        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading1'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=12,
            spaceBefore=18,
            leftIndent=0
        ))

        self.styles.add(ParagraphStyle(
            name='Footer',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#7f8c8d'),
            alignment=TA_CENTER
        ))

    def generate_pdf(
        self,
        minutes: BoardMinutes_v1,
        output_path: str,
        credential: Optional[Dict[str, Any]] = None,
        proof: Optional[Dict[str, Any]] = None,
        anchor_receipt: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate PDF from board minutes."""

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            topMargin=72,
            bottomMargin=72,
            leftMargin=72,
            rightMargin=72
        )

        story = []

        story.append(Paragraph(minutes.title, self.styles['CustomTitle']))

        meeting_info = f"<b>Date:</b> {minutes.date}<br/>"
        meeting_info += f"<b>Attendees:</b> {', '.join(minutes.attendees)}<br/>"
        if minutes.absent:
            meeting_info += f"<b>Absent:</b> {', '.join(minutes.absent)}<br/>"

        story.append(Paragraph(meeting_info, self.styles['Normal']))
        story.append(Spacer(1, 0.3 * inch))

        if minutes.agenda:
            story.append(Paragraph("Agenda", self.styles['SectionHeader']))
            for i, item in enumerate(minutes.agenda, 1):
                story.append(Paragraph(f"{i}. {item.item}", self.styles['Normal']))
            story.append(Spacer(1, 0.2 * inch))

        if minutes.motions:
            story.append(Paragraph("Motions", self.styles['SectionHeader']))
            motion_data = []
            motion_data.append(['Motion', 'Moved By', 'Seconded By', 'Result'])

            for motion in minutes.motions:
                motion_data.append([
                    Paragraph(motion.text[:100] + "..." if len(motion.text) > 100 else motion.text,
                             self.styles['Normal']),
                    motion.movedBy or "—",
                    motion.secondedBy or "—",
                    motion.vote.result
                ])

            motion_table = Table(motion_data, colWidths=[3.5*inch, 1.5*inch, 1.5*inch, 1*inch])
            motion_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(motion_table)
            story.append(Spacer(1, 0.3 * inch))

        if minutes.decisions:
            story.append(Paragraph("Decisions", self.styles['SectionHeader']))
            for i, decision in enumerate(minutes.decisions, 1):
                story.append(Paragraph(f"{i}. {decision.text}", self.styles['Normal']))
            story.append(Spacer(1, 0.2 * inch))

        if minutes.actions:
            story.append(Paragraph("Action Items", self.styles['SectionHeader']))
            action_data = []
            action_data.append(['Action', 'Owner', 'Due Date'])

            for action in minutes.actions:
                action_data.append([
                    Paragraph(action.text, self.styles['Normal']),
                    action.owner,
                    action.due or "TBD"
                ])

            action_table = Table(action_data, colWidths=[4*inch, 1.5*inch, 1.5*inch])
            action_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(action_table)
            story.append(Spacer(1, 0.3 * inch))

        if minutes.notes:
            story.append(Paragraph("Original Transcript", self.styles['SectionHeader']))
            story.append(Spacer(1, 0.2 * inch))

            # Display the transcript exactly as provided, line by line
            for line in minutes.notes.split('\n'):
                # Escape XML special characters for reportlab
                line_escaped = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

                # Use preformatted style to preserve spacing
                if line.strip():
                    story.append(Paragraph(line_escaped, self.styles['Normal']))
                else:
                    # Add space for blank lines
                    story.append(Spacer(1, 0.1 * inch))

            story.append(Spacer(1, 0.3 * inch))

        story.append(Spacer(1, 0.5 * inch))

        # Add comprehensive hash stamp footer
        from datetime import datetime, timezone
        stamp_time = datetime.now(timezone.utc).isoformat()

        story.append(Paragraph("─" * 80, self.styles['Normal']))
        story.append(Paragraph("CRYPTOGRAPHIC VERIFICATION STAMP", self.styles['SectionHeader']))

        footer_text = "<b>Generated by BlackBox</b><br/>"
        footer_text += f"<b>Stamped at:</b> {stamp_time}<br/><br/>"

        if credential:
            footer_text += "<b>Document Hashes:</b><br/>"
            footer_text += f"SHA-256: {credential.get('sha256', '')}<br/>"
            footer_text += f"BLAKE3: {credential.get('blake3', '')}<br/><br/>"

            footer_text += "<b>Digital Signature:</b><br/>"
            footer_text += f"Public Key: {credential.get('signer', {}).get('publicKey', '')}<br/>"
            footer_text += f"Signature: {credential.get('signature', '')[:32]}...<br/><br/>"

        if proof:
            footer_text += "<b>Merkle Tree Verification:</b><br/>"
            footer_text += f"Root Hash: {proof.get('merkleRoot', '')}<br/>"
            footer_text += f"Leaf Count: {len(proof.get('leaves', []))}<br/><br/>"

        if anchor_receipt:
            footer_text += "<b>Blockchain Anchor:</b><br/>"
            footer_text += f"Transaction: {anchor_receipt.get('txHash', '')}<br/>"
            footer_text += f"Chain ID: {anchor_receipt.get('chainId', '')}<br/>"
            footer_text += f"Contract: {anchor_receipt.get('contractAddress', '')}<br/>"

        story.append(Paragraph(footer_text, self.styles['Footer']))
        story.append(Paragraph("─" * 80, self.styles['Normal']))

        doc.build(story)

        return output_path