"""Original synthetic PDF fixtures; same first-party license as this repository.

No downloaded book, commercial font, image or external resource is embedded.
"""
import io

from pypdf import PdfWriter
from pypdf.constants import PageLabelStyle
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject


def synthetic_pdf(*, pages=12, empty_page=3, image_page=4, two_columns=5, encrypted=False):
    writer = PdfWriter()
    cmap = DecodedStreamObject()
    cmap.set_data(b'/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def /CMapName /Test def /CMapType 2 def 1 begincodespacerange <00> <FF> endcodespacerange 1 beginbfchar <80> <FB01> endbfchar endcmap end end')
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'), NameObject('/Encoding'): NameObject('/WinAnsiEncoding'),
        NameObject('/ToUnicode'): writer._add_object(cmap)})
    for index in range(pages):
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
        if index == empty_page:
            continue
        if index == image_page:
            image = DecodedStreamObject()
            image.set_data(bytes([255, 0, 0]))
            image.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
                NameObject('/Width'): NumberObject(1), NameObject('/Height'): NumberObject(1),
                NameObject('/ColorSpace'): NameObject('/DeviceRGB'), NameObject('/BitsPerComponent'): NumberObject(8)})
            page['/Resources'][NameObject('/XObject')] = DictionaryObject({NameObject('/Im1'): writer._add_object(image)})
            data = b'q 100 0 0 100 72 600 cm /Im1 Do Q'
        else:
            title = 'Sumário' if index == 0 else f'Capítulo na página física {index + 1}'
            if index in {6, 7}:
                title = f'Capítulo contínuo, parte {index - 5}'
            data = b'BT /F1 12 Tf 72 720 Td (' + title.encode('cp1252') + b') Tj 0 -24 Td <4C6967617475726120806E616C> Tj ET'
            if index == two_columns:
                data += b' BT /F1 12 Tf 72 650 Td (Esquerda) Tj 300 0 Td (Direita) Tj ET'
        stream = DecodedStreamObject()
        stream.set_data(data)
        page[NameObject('/Contents')] = writer._add_object(stream)
    if pages >= 3:
        writer.set_page_label(0, 1, style=PageLabelStyle.LOWERCASE_ROMAN, start=1)
        writer.set_page_label(2, pages - 1, style=PageLabelStyle.DECIMAL, start=1)
    if encrypted:
        writer.encrypt('fixture-password')
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def pageindex_outline_pdf():
    """Small first-party PDF with page and font evidence for PageIndex Flash."""
    writer = PdfWriter()
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'), NameObject('/Encoding'): NameObject('/WinAnsiEncoding')})
    font_ref = writer._add_object(font)
    pages = (
        (("Sample Technical Report", 30, 72, 720), ("Executive Summary", 20, 72, 650),
         ("This report explains the sample dataset and results.", 12, 72, 610)),
        (("1 Introduction", 22, 72, 720), ("The introduction describes the problem and intended use.", 12, 72, 670),
         ("The following sections define scope and method.", 12, 72, 650)),
        (("2 Methods", 22, 72, 720), ("2.1 Data", 17, 72, 670),
         ("Measurements use a fixed public sample and repeatable steps.", 12, 72, 630),
         ("2.2 Review", 17, 72, 570), ("Results were reviewed against recorded source data.", 12, 72, 530)),
    )
    for lines in pages:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font_ref})})
        commands = []
        for text, size, x, y in lines:
            escaped = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            commands.append(f'BT /F1 {size} Tf {x} {y} Td ({escaped}) Tj ET')
        stream = DecodedStreamObject()
        stream.set_data('\n'.join(commands).encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
