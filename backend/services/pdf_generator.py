"""
PDF Generator for Swedish Annual Reports (Årsredovisning)
Generates a professional PDF with all sections in the correct order
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import os


class AnnualReportPDFGenerator:
    """Generate PDF for Swedish Annual Reports"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()
    
    def _setup_styles(self):
        """Setup custom styles for Swedish annual reports"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=12,
            alignment=1,  # Center
            fontName='Helvetica-Bold'
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#2c3e50'),
            spaceAfter=10,
            spaceBefore=10,
            fontName='Helvetica-Bold'
        ))
        
        # Subsection header style
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#34495e'),
            spaceAfter=8,
            spaceBefore=8,
            fontName='Helvetica-Bold'
        ))
        
        # Body text style
        self.styles.add(ParagraphStyle(
            name='BodyText',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#333333'),
            spaceAfter=6,
            fontName='Helvetica'
        ))
        
        # Table header style
        self.styles.add(ParagraphStyle(
            name='TableHeader',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#ffffff'),
            fontName='Helvetica-Bold'
        ))
    
    def _format_amount(self, amount):
        """Format amount in Swedish style (space as thousand separator)"""
        if amount is None or amount == '':
            return '0'
        try:
            num = float(amount)
            # Format with space as thousand separator
            formatted = f"{int(num):,}".replace(',', ' ')
            return formatted
        except (ValueError, TypeError):
            return '0'
    
    def _create_company_header(self, company_data):
        """Create company header section"""
        elements = []
        
        # Company name and org number
        company_name = company_data.get('company_name', 'Företag AB')
        org_number = company_data.get('organization_number', '')
        fiscal_year = company_data.get('fiscal_year', datetime.now().year)
        
        elements.append(Paragraph(f"<b>{company_name}</b>", self.styles['ReportTitle']))
        elements.append(Paragraph(f"Organisationsnummer: {org_number}", self.styles['BodyText']))
        elements.append(Paragraph(f"Räkenskapsår {fiscal_year}", self.styles['BodyText']))
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_forvaltningsberattelse(self, company_data):
        """Create Förvaltningsberättelse section"""
        elements = []
        
        elements.append(Paragraph("Förvaltningsberättelse", self.styles['SectionHeader']))
        elements.append(Spacer(1, 10))
        
        # Information om verksamheten
        elements.append(Paragraph("Information om verksamheten", self.styles['SubsectionHeader']))
        verksamhet = company_data.get('verksamhetsbeskrivning', 
            'Bolaget bedriver verksamhet inom...')
        elements.append(Paragraph(verksamhet, self.styles['BodyText']))
        elements.append(Spacer(1, 10))
        
        # Väsentliga händelser
        if company_data.get('hasEvents'):
            elements.append(Paragraph("Väsentliga händelser", self.styles['SubsectionHeader']))
            events = company_data.get('significantEvents', 'Inga väsentliga händelser att rapportera.')
            elements.append(Paragraph(events, self.styles['BodyText']))
            elements.append(Spacer(1, 10))
        
        # Förändring i eget kapital
        fb_table = company_data.get('fbTable', [])
        if fb_table and len(fb_table) > 0:
            elements.append(Paragraph("Förändring i eget kapital", self.styles['SubsectionHeader']))
            elements.extend(self._create_fb_table(fb_table))
            elements.append(Spacer(1, 10))
        
        # Förslag till vinstdisposition
        elements.append(Paragraph("Förslag till vinstdisposition", self.styles['SubsectionHeader']))
        
        fb_variables = company_data.get('fbVariables', {})
        balanserat_resultat = fb_variables.get('balanserat_resultat_row3', 0)
        arets_resultat = fb_variables.get('arets_resultat_row3', 0)
        total = balanserat_resultat + arets_resultat
        
        disposition_text = f"""
        Till årsstämmans förfogande står följande vinstmedel:<br/>
        Balanserat resultat: {self._format_amount(balanserat_resultat)} kr<br/>
        Årets resultat: {self._format_amount(arets_resultat)} kr<br/>
        Summa: {self._format_amount(total)} kr<br/>
        <br/>
        Styrelsen föreslår att vinstmedlen disponeras enligt följande:<br/>
        I ny räkning överföres: {self._format_amount(total)} kr
        """
        elements.append(Paragraph(disposition_text, self.styles['BodyText']))
        
        return elements
    
    def _create_fb_table(self, fb_table):
        """Create Förändring i eget kapital table"""
        elements = []
        
        # Table headers
        headers = ['', 'Aktiekapital', 'Reservfond', 'Balanserat resultat', 'Årets resultat', 'Summa']
        
        # Prepare table data
        table_data = [headers]
        for row in fb_table:
            table_data.append([
                row.get('label', ''),
                self._format_amount(row.get('aktiekapital', 0)),
                self._format_amount(row.get('reservfond', 0)),
                self._format_amount(row.get('balanserat_resultat', 0)),
                self._format_amount(row.get('arets_resultat', 0)),
                self._format_amount(row.get('total', 0))
            ])
        
        # Create table
        table = Table(table_data, colWidths=[6*cm, 2.5*cm, 2.5*cm, 3*cm, 2.5*cm, 2.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        return elements
    
    def _create_resultatrakning(self, rr_data, fiscal_year):
        """Create Resultaträkning (Income Statement) section"""
        elements = []
        
        elements.append(Paragraph("Resultaträkning", self.styles['SectionHeader']))
        elements.append(Spacer(1, 10))
        
        # Prepare table data
        headers = ['', f'{fiscal_year}', f'{fiscal_year - 1}', 'Not']
        table_data = [headers]
        
        for item in rr_data:
            if not item.get('row_title'):
                continue
            
            label = item.get('label', item.get('row_title', ''))
            current = self._format_amount(item.get('current_amount', 0))
            previous = self._format_amount(item.get('previous_amount', 0))
            note = str(item.get('br_not', '')) if item.get('br_not') else ''
            
            # Apply styling based on item type
            if item.get('header'):
                label = f"<b>{label}</b>"
            elif item.get('style') == 'SUM':
                label = f"<b>{label}</b>"
            
            table_data.append([label, current, previous, note])
        
        # Create table
        table = Table(table_data, colWidths=[10*cm, 3*cm, 3*cm, 2*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        return elements
    
    def _create_balansrakning_tillgangar(self, br_data, fiscal_year):
        """Create Balansräkning - Tillgångar (Assets) section"""
        elements = []
        
        elements.append(Paragraph("Balansräkning - Tillgångar", self.styles['SectionHeader']))
        elements.append(Spacer(1, 10))
        
        # Filter for assets (typically rows up to a certain point in BR)
        # Assets are typically before "Eget kapital och skulder"
        assets = []
        for item in br_data:
            variable_name = item.get('variable_name', '')
            # Stop when we reach equity/liabilities section
            if variable_name in ['EgetKapital', 'SumEgetKapital', 'Skulder']:
                break
            if item.get('row_title'):
                assets.append(item)
        
        # Prepare table data
        headers = ['TILLGÅNGAR', f'{fiscal_year}', f'{fiscal_year - 1}', 'Not']
        table_data = [headers]
        
        for item in assets:
            label = item.get('label', item.get('row_title', ''))
            current = self._format_amount(item.get('current_amount', 0))
            previous = self._format_amount(item.get('previous_amount', 0))
            note = str(item.get('br_not', '')) if item.get('br_not') else ''
            
            # Apply styling based on item type
            if item.get('header'):
                label = f"<b>{label}</b>"
            elif item.get('style') == 'SUM':
                label = f"<b>{label}</b>"
            
            table_data.append([label, current, previous, note])
        
        # Create table
        table = Table(table_data, colWidths=[10*cm, 3*cm, 3*cm, 2*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        return elements
    
    def _create_balansrakning_eget_kapital_skulder(self, br_data, fiscal_year):
        """Create Balansräkning - Eget kapital och skulder section"""
        elements = []
        
        elements.append(Paragraph("Balansräkning - Eget kapital och skulder", 
                                 self.styles['SectionHeader']))
        elements.append(Spacer(1, 10))
        
        # Filter for equity and liabilities (starts from EgetKapital section)
        equity_and_liabilities = []
        found_equity = False
        for item in br_data:
            variable_name = item.get('variable_name', '')
            # Start when we reach equity section
            if variable_name in ['EgetKapital', 'SumEgetKapital'] or 'Eget kapital' in item.get('row_title', ''):
                found_equity = True
            
            if found_equity and item.get('row_title'):
                equity_and_liabilities.append(item)
        
        # Prepare table data
        headers = ['EGET KAPITAL OCH SKULDER', f'{fiscal_year}', f'{fiscal_year - 1}', 'Not']
        table_data = [headers]
        
        for item in equity_and_liabilities:
            label = item.get('label', item.get('row_title', ''))
            current = self._format_amount(item.get('current_amount', 0))
            previous = self._format_amount(item.get('previous_amount', 0))
            note = str(item.get('br_not', '')) if item.get('br_not') else ''
            
            # Apply styling based on item type
            if item.get('header'):
                label = f"<b>{label}</b>"
            elif item.get('style') == 'SUM':
                label = f"<b>{label}</b>"
            
            table_data.append([label, current, previous, note])
        
        # Create table
        table = Table(table_data, colWidths=[10*cm, 3*cm, 3*cm, 2*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        elements.append(table)
        return elements
    
    def _create_noter(self, noter_data, fiscal_year):
        """Create Noter (Notes) section"""
        elements = []
        
        elements.append(Paragraph("Noter", self.styles['SectionHeader']))
        elements.append(Spacer(1, 10))
        
        if not noter_data or len(noter_data) == 0:
            elements.append(Paragraph("Inga noter att visa.", self.styles['BodyText']))
            return elements
        
        # Group notes by block
        notes_by_block = {}
        for item in noter_data:
            if not item.get('always_show') and not item.get('toggle_show'):
                continue
            
            block = item.get('block', 'OTHER')
            if block not in notes_by_block:
                notes_by_block[block] = []
            notes_by_block[block].append(item)
        
        # Generate notes for each block
        note_number = 1
        for block, items in sorted(notes_by_block.items()):
            for item in items:
                row_title = item.get('row_title', '')
                current = self._format_amount(item.get('current_amount', 0))
                previous = self._format_amount(item.get('previous_amount', 0))
                
                elements.append(Paragraph(f"<b>Not {note_number} - {row_title}</b>", 
                                        self.styles['SubsectionHeader']))
                
                # Create simple table for note amounts
                note_table_data = [
                    ['', f'{fiscal_year}', f'{fiscal_year - 1}'],
                    [row_title, current, previous]
                ]
                
                note_table = Table(note_table_data, colWidths=[10*cm, 3*cm, 3*cm])
                note_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8e8e8')),
                    ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                    ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                ]))
                
                elements.append(note_table)
                elements.append(Spacer(1, 10))
                note_number += 1
        
        return elements
    
    def generate_pdf(self, output_path, company_data, rr_data, br_data, noter_data):
        """
        Generate the complete annual report PDF
        
        Args:
            output_path: Path where PDF will be saved
            company_data: Dictionary with company information
            rr_data: Resultaträkning data (Income Statement)
            br_data: Balansräkning data (Balance Sheet)
            noter_data: Noter data (Notes)
        """
        # Create PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # Build content
        story = []
        
        # Company header
        story.extend(self._create_company_header(company_data))
        
        # 1. Förvaltningsberättelse
        story.extend(self._create_forvaltningsberattelse(company_data))
        story.append(PageBreak())
        
        # 2. Resultaträkning
        fiscal_year = company_data.get('fiscal_year', datetime.now().year)
        story.extend(self._create_resultatrakning(rr_data, fiscal_year))
        story.append(PageBreak())
        
        # 3. Balansräkning - Tillgångar
        story.extend(self._create_balansrakning_tillgangar(br_data, fiscal_year))
        story.append(PageBreak())
        
        # 4. Balansräkning - Eget kapital och skulder
        story.extend(self._create_balansrakning_eget_kapital_skulder(br_data, fiscal_year))
        story.append(PageBreak())
        
        # 5. Noter
        story.extend(self._create_noter(noter_data, fiscal_year))
        
        # Build PDF
        doc.build(story)
        
        return output_path

