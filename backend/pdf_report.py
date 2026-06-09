import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from datetime import datetime

class NumberedCanvas(canvas.Canvas):
    """
    Canvas to calculate total page count dynamically and print footers with page numbers.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Draw a thin header separator line on later pages
        if self._pageNumber > 1:
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, 750, 558, 750)
            self.drawString(54, 755, "AI-Powered MoM Assistant - Minutes of Meeting")
            
        # Draw footer line
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 50, 558, 50)
        
        # Draw footer text
        self.drawString(54, 38, f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 38, page_str)
        self.restoreState()


def generate_mom_pdf(meeting, output_path):
    """
    Generates a professional PDF document for the meeting minutes.
    meeting is a dictionary containing all meeting data from the database.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 54pt margin = 0.75 in
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=64
    )

    styles = getSampleStyleSheet()
    
    # Define custom colors
    primary_color = colors.HexColor("#4F46E5")   # Indigo
    secondary_color = colors.HexColor("#0F172A") # Slate 900
    text_color = colors.HexColor("#334155")      # Slate 700
    bg_light = colors.HexColor("#F8FAFC")        # Slate 50
    border_color = colors.HexColor("#E2E8F0")    # Slate 200
    accent_color = colors.HexColor("#10B981")    # Emerald (for decisions)
    
    # Modify or add styles
    styles['Normal'].textColor = text_color
    styles['Normal'].fontSize = 10
    styles['Normal'].leading = 14

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=secondary_color,
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=primary_color,
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=secondary_color,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'BulletCustom',
        parent=styles['Normal'],
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    decision_style = ParagraphStyle(
        'DecisionCustom',
        parent=styles['Normal'],
        leftIndent=15,
        firstLineIndent=-10,
        textColor=colors.HexColor("#065F46"), # Dark green text
        fontName='Helvetica-Bold',
        spaceAfter=5
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.white
    )
    
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=9,
        leading=12
    )

    story = []

    # Title & Subtitle
    story.append(Paragraph("MINUTES OF MEETING", title_style))
    story.append(Paragraph(meeting['title'], subtitle_style))
    
    # Metadata Table
    # Format Date
    try:
        dt = datetime.fromisoformat(meeting['date'])
        date_str = dt.strftime("%B %d, %Y - %I:%M %p")
    except Exception:
        date_str = meeting['date']
        
    duration_min = meeting['duration'] // 60
    duration_sec = meeting['duration'] % 60
    duration_str = f"{duration_min} min {duration_sec} sec" if duration_min > 0 else f"{duration_sec} sec"
    
    metadata_data = [
        [
            Paragraph("<b>Date & Time:</b>", body_style), Paragraph(date_str, body_style),
            Paragraph("<b>Duration:</b>", body_style), Paragraph(duration_str, body_style)
        ],
        [
            Paragraph("<b>Status:</b>", body_style), Paragraph(meeting['status'].capitalize(), body_style),
            Paragraph("<b>Source:</b>", body_style), Paragraph("Microphone Audio File" if meeting.get('audio_path') else "Uploaded Audio File", body_style)
        ]
    ]
    
    meta_table = Table(metadata_data, colWidths=[90, 160, 70, 184])
    meta_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
        ('PADDING', (0,0), (-1,-1), 8),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, border_color),
        ('LINEABOVE', (0,0), (-1,-1), 0.5, border_color),
        ('LINELEFT', (0,0), (-1,-1), 0.5, border_color),
        ('LINERIGHT', (0,0), (-1,-1), 0.5, border_color),
    ]))
    
    story.append(meta_table)
    story.append(Spacer(1, 15))

    # Fetch summary structure
    summary = meeting.get('summary', {})
    if not isinstance(summary, dict):
        summary = {}

    # 1. Executive Summary / Overview
    story.append(Paragraph("Executive Summary", h1_style))
    overview_text = summary.get('overview', "No overview available.")
    story.append(Paragraph(overview_text, body_style))
    story.append(Spacer(1, 10))

    # 2. Key Discussion Points
    story.append(Paragraph("Key Discussion Points", h1_style))
    points = summary.get('key_points', [])
    if points:
        for pt in points:
            story.append(Paragraph(f"&bull; {pt}", bullet_style))
    else:
        story.append(Paragraph("No discussion points recorded.", bullet_style))
    story.append(Spacer(1, 10))

    # 3. Key Decisions Made
    story.append(Paragraph("Decisions Made", h1_style))
    decisions = summary.get('decisions', [])
    if decisions:
        for dec in decisions:
            story.append(Paragraph(f"&#10004; {dec}", decision_style))
    else:
        story.append(Paragraph("No decisions recorded during the meeting.", bullet_style))
    story.append(Spacer(1, 10))

    # 4. Action Items (Table)
    story.append(Paragraph("Action Items", h1_style))
    action_items = summary.get('action_items', [])
    if action_items:
        # Table Header
        action_data = [[
            Paragraph("Action Task", table_header_style), 
            Paragraph("Assignee", table_header_style), 
            Paragraph("Deadline", table_header_style)
        ]]
        
        # Populate Table Rows
        for item in action_items:
            task = item.get('task', 'N/A')
            assignee = item.get('assignee', 'Unassigned')
            deadline = item.get('deadline', 'N/A')
            
            action_data.append([
                Paragraph(task, table_cell_style),
                Paragraph(assignee, table_cell_style),
                Paragraph(deadline, table_cell_style)
            ])
            
        action_table = Table(action_data, colWidths=[300, 100, 104])
        action_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), primary_color),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('PADDING', (0,0), (-1,-1), 6),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
            ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ]))
        story.append(action_table)
    else:
        story.append(Paragraph("No action items assigned.", bullet_style))
    story.append(Spacer(1, 15))

    # 5. Transcript
    story.append(Paragraph("Full Meeting Transcript", h1_style))
    raw_transcript = meeting.get('transcript', "")
    if raw_transcript:
        # Process transcript paragraph by paragraph
        paras = raw_transcript.split('\n')
        for para in paras:
            para = para.strip()
            if not para:
                continue
            # Format speaker labels differently if present
            if ":" in para and not para.startswith("http"):
                parts = para.split(":", 1)
                speaker, text = parts[0], parts[1]
                formatted_para = f"<b>{speaker}:</b>{text}"
            else:
                formatted_para = para
            story.append(Paragraph(formatted_para, body_style))
    else:
        story.append(Paragraph("Transcript unavailable.", bullet_style))

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
