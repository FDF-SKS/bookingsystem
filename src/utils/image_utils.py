import io
import uuid

from django.core.files.base import ContentFile
from PIL import Image


def process_image(image_field, instance):
    # Rename the image
    new_filename = f"{instance.id}-{instance.name}-{uuid.uuid4()}.jpg"
    image_field.name = new_filename

    # Resize the image
    image = Image.open(image_field)

    # Convert image to RGB if it's not already (to handle PNG, etc.)
    if image.mode != 'RGB':
        image = image.convert('RGB')

    # Define the maximum size
    max_size = (800, 800)

    # Resize the image while maintaining the aspect ratio
    image.thumbnail(max_size, Image.LANCZOS)

    # Save the resized image to a BytesIO object
    image_io = io.BytesIO()
    image.save(image_io, format='JPEG')
    image_content = ContentFile(image_io.getvalue(), new_filename)

    return new_filename, image_content

