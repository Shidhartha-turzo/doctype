"""
Print format rendering engine.

Renders a document into a printable HTML page using a configured PrintFormat,
or a generic field table when none is defined. PDF output is optional and only
available when the ``xhtml2pdf`` package is installed (pure-pip, no system
libraries); browsers can also print/save the HTML view to PDF directly.

PrintFormat templates are authored by admins and rendered with the Django
template engine against a restricted context (doc, data, fields, document).
"""
import io
import logging

from django.template import Context, Template
from django.utils.html import escape

from .engine_models import PrintFormat

logger = logging.getLogger(__name__)

# Map PrintFormat.page_size to a CSS @page size keyword.
_PAGE_CSS = {'A4': 'A4', 'Letter': 'letter', 'Legal': 'legal'}


class PrintError(Exception):
    """Raised when a document cannot be rendered for print."""
    pass


class PrintService:
    """Stateless service for rendering printable documents."""

    @classmethod
    def pdf_available(cls):
        try:
            import xhtml2pdf  # noqa: F401
            return True
        except ImportError:
            return False

    @classmethod
    def get_format(cls, doctype, format_id=None):
        """
        Resolve the PrintFormat to use. An explicit id must belong to the
        doctype; otherwise the default (or first active) format is used. May
        return None, in which case a generic layout is rendered.
        """
        if format_id:
            try:
                return PrintFormat.objects.get(id=format_id, doctype=doctype, is_active=True)
            except PrintFormat.DoesNotExist:
                raise PrintError('Print format not found for this doctype.')
        return (
            PrintFormat.objects.filter(doctype=doctype, is_active=True, is_default=True).first()
            or PrintFormat.objects.filter(doctype=doctype, is_active=True).first()
        )

    @classmethod
    def render_html(cls, document, format_id=None):
        """Render the full printable HTML page for a document."""
        doctype = document.doctype
        print_format = cls.get_format(doctype, format_id)
        fields = (doctype.schema or {}).get('fields', [])
        body = cls._render_body(print_format, document, fields)
        return cls._wrap_page(print_format, document, body)

    @classmethod
    def render_pdf(cls, document, format_id=None):
        """Render a document to PDF bytes (requires xhtml2pdf)."""
        try:
            from xhtml2pdf import pisa
        except ImportError:
            raise PrintError(
                'PDF generation requires the optional "xhtml2pdf" package. '
                'Use the HTML view and print/save as PDF from the browser instead.'
            )
        html = cls.render_html(document, format_id)
        buffer = io.BytesIO()
        result = pisa.CreatePDF(src=html, dest=buffer, encoding='utf-8')
        if result.err:
            raise PrintError('PDF generation failed.')
        return buffer.getvalue()

    @classmethod
    def _render_body(cls, print_format, document, fields):
        if print_format and print_format.template and print_format.template.strip():
            context = {
                'doc': document,
                'data': document.data or {},
                'fields': fields,
                'document': document,
            }
            try:
                return Template(print_format.template).render(Context(context))
            except Exception as e:
                raise PrintError(f'Template error: {e}')
        return cls._generic_body(document, fields)

    @classmethod
    def _generic_body(cls, document, fields):
        """A plain label/value table used when no template is configured."""
        data = document.data or {}
        rows = []
        for f in fields:
            label = escape(str(f.get('label', f['name'])))
            value = data.get(f['name'], '')
            rows.append(
                f'<tr>'
                f'<th style="text-align:left;padding:6px;border:1px solid #ddd;'
                f'background:#f7f7f7;width:30%;">{label}</th>'
                f'<td style="padding:6px;border:1px solid #ddd;">{escape(str(value))}</td>'
                f'</tr>'
            )
        return (
            f'<h2 style="margin:0 0 12px;">{escape(str(document.name))}</h2>'
            f'<table style="border-collapse:collapse;width:100%;">{"".join(rows)}</table>'
        )

    @classmethod
    def _wrap_page(cls, print_format, document, body):
        page_size = print_format.page_size if print_format else 'A4'
        pdf_size = _PAGE_CSS.get(page_size, 'A4')
        letterhead = print_format.letterhead if print_format else ''
        header = print_format.header if print_format else ''
        footer = print_format.footer if print_format else ''
        extra_css = print_format.css if print_format else ''
        return (
            '<!DOCTYPE html>\n'
            '<html><head><meta charset="utf-8">'
            f'<title>{escape(str(document.name))}</title>\n'
            '<style>\n'
            f'@page {{ size: {pdf_size}; margin: 1.5cm; }}\n'
            'body { font-family: Arial, Helvetica, sans-serif; color:#222; font-size:13px; }\n'
            '.print-letterhead { margin-bottom:16px; }\n'
            '.print-footer { margin-top:24px; font-size:11px; color:#666; }\n'
            '@media print { .no-print { display:none; } }\n'
            f'{extra_css}\n'
            '</style></head>\n'
            '<body>\n'
            f'<div class="print-letterhead">{letterhead}</div>\n'
            f'<div class="print-header">{header}</div>\n'
            f'<div class="print-body">{body}</div>\n'
            f'<div class="print-footer">{footer}</div>\n'
            '</body></html>'
        )
