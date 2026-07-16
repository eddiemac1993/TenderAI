from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

from core.pdf import build_pdf_response, styles
from bid_generator.services import expanded_tender_xml_items
from .zppa_scraper import zppa_detail_value


def generate_xml_structure_pdf(tender):
    style = styles()
    elements = [
        Paragraph('Tender XML Structure and Payment Summary', style['Heading1']),
        Paragraph(
            'This report is generated from the public ZPPA tender details and Tender Structure XML captured by TenderAI. '
            'Use it as a working checklist before preparing bid documents.',
            style['BodyText'],
        ),
        Spacer(1, 10),
    ]
    elements.append(tender_summary_table(tender, style))
    elements.append(Spacer(1, 14))
    elements.append(Paragraph('Payment / Fee Information', style['Heading2']))
    elements.append(payment_table(tender, style))
    elements.append(Spacer(1, 14))
    elements.append(Paragraph('XML Bid Structure', style['Heading2']))

    expanded_items = expanded_tender_xml_items(tender)
    if not expanded_items:
        elements.append(Paragraph('No Tender Structure XML items have been fetched or uploaded yet.', style['BodyText']))
    else:
        for envelope, items in grouped_xml_items(expanded_items):
            elements.append(Spacer(1, 8))
            elements.append(Paragraph(safe_text(envelope or 'Bid requirements'), style['Heading3']))
            rows = [['No.', 'Requirement', 'Expected response / attachment', 'Mandatory']]
            for item in items:
                response_lines = item.get('response_items') or []
                response = '<br/>'.join(safe_text(line) for line in response_lines)
                if not response:
                    response = safe_text(item.get('response') or 'Complete / attach as required')
                rows.append([
                    safe_text(item.get('order') or ''),
                    Paragraph(safe_text(item.get('requirement') or item.get('title') or '-'), style['BodyText']),
                    Paragraph(response, style['BodyText']),
                    'Yes' if item.get('mandatory') else 'No',
                ])
            elements.append(Table(rows, colWidths=[35, 155, 245, 40], style=xml_table_style()))

    return build_pdf_response(elements, f'XML Structure - {tender.title}')


def tender_summary_table(tender, style):
    rows = [
        ['Tender title', Paragraph(safe_text(tender.title), style['BodyText'])],
        ['Procuring entity', safe_text(tender.procuring_entity or '-')],
        ['Tender number / unique ID', safe_text(tender.tender_number or '-')],
        ['ZPPA resource ID', safe_text(tender.zppa_resource_id or '-')],
        ['Procurement method', safe_text(tender.procurement_method or '-')],
        ['Submission method', safe_text(tender.submission_method or '-')],
        ['Published', tender.published_at.strftime('%d/%m/%Y %H:%M') if tender.published_at else '-'],
        ['Closing', tender.closing_at.strftime('%d/%m/%Y %H:%M') if tender.closing_at else (tender.closing_date or '-')],
    ]
    return Table(rows, colWidths=[150, 325], style=xml_table_style())


def payment_table(tender, style):
    payment_type = zppa_detail_value(tender.zppa_details or [], 'Payment Type') or '-'
    payment_terms = zppa_detail_value(tender.zppa_details or [], 'Payment Terms and Method', 'Payment Terms') or '-'
    rows = [
        ['Payment type', Paragraph(safe_text(payment_type), style['BodyText'])],
        ['Participation fee / payment amount', payment_amount_label(tender)],
        ['Payment terms and method', Paragraph(safe_text(payment_terms), style['BodyText'])],
        ['Bid security', safe_text(tender.bid_security_amount or 'Check XML / solicitation document')],
    ]
    return Table(rows, colWidths=[170, 305], style=xml_table_style())


def payment_amount_label(tender):
    if tender.participation_fee:
        return f'ZMW {tender.participation_fee:,.2f}'
    amount = zppa_detail_value(tender.zppa_details or [], 'Payment Amount (ZMW)', 'Payment Amount', 'Participation Fee')
    return safe_text(amount or 'Not detected')


def grouped_xml_items(items):
    groups = []
    group_map = {}
    for item in items or []:
        envelope = item.get('envelope') or 'Bid requirements'
        if envelope not in group_map:
            group_map[envelope] = []
            groups.append((envelope, group_map[envelope]))
        group_map[envelope].append(item)
    return groups


def safe_text(value):
    return escape(str(value or ''))


def xml_table_style():
    return TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.45, colors.HexColor('#d9e2ec')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#edf4f3')),
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('LEADING', (0, 0), (-1, -1), 10.5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ])
