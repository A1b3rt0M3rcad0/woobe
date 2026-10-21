"""First-party image/PDF OCR fixtures. No external document or image is used."""
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pypdf import PdfReader, PdfWriter, Transformation

from tests.fixtures.artifacts.pdf_sources import synthetic_pdf


PORTUGUESE = ('Ação e educação em português.', 'João lê a apostila de matemática.',
              'A figura contém números: 12345.', 'Documento de teste local da Woobe.')


def portuguese_image(*, rotate=0, poor=False, dense=False):
    font_path = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not font_path.is_file():
        raise RuntimeError('Real Portuguese OCR fixtures require fonts-dejavu-core')
    lines = PORTUGUESE * (10 if dense else 1)
    image = Image.new('RGB', (1800, 3600 if dense else 500), 'white')
    ImageDraw.Draw(image).multiline_text((50, 50), '\n'.join(lines), fill='black',
        font=ImageFont.truetype(str(font_path), 48), spacing=22)
    try:
        if poor:
            reduced = image.resize((90, 25)).filter(ImageFilter.GaussianBlur(3))
            image.close()
            image = reduced.resize((1800, 500))
            reduced.close()
        if rotate:
            rotated = image.rotate(rotate, expand=True)
            image.close()
            image = rotated
        output = io.BytesIO()
        image.save(output, format='PNG', dpi=(150, 150))
        return output.getvalue()
    finally:
        image.close()


def hybrid_pdf():
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(synthetic_pdf(pages=1, empty_page=None, image_page=None, two_columns=None))))
    with Image.open(io.BytesIO(portuguese_image())) as image:
        scan = io.BytesIO()
        image.save(scan, format='PDF', resolution=150)
    writer.append(PdfReader(io.BytesIO(scan.getvalue())))
    writer.add_blank_page(width=612, height=792)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def portuguese_jpeg_with_exif_rotation():
    with Image.open(io.BytesIO(portuguese_image())) as source:
        image = source.rotate(180)
        try:
            exif = Image.Exif()
            exif[274] = 3
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=95, exif=exif)
            return output.getvalue()
        finally:
            image.close()


def hybrid_page_pdf():
    writer = PdfWriter()
    writer.append(PdfReader(io.BytesIO(synthetic_pdf(pages=1, empty_page=None, image_page=None, two_columns=None))))
    with Image.open(io.BytesIO(portuguese_image())) as image:
        scan = io.BytesIO()
        image.save(scan, format='PDF', resolution=150)
    page = PdfReader(io.BytesIO(scan.getvalue())).pages[0]
    writer.pages[0].merge_transformed_page(page, Transformation().scale(.65).translate(48, 350))
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
