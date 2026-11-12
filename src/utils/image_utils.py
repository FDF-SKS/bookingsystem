import io
import uuid

from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
THUMBNAIL_SIZE = (800, 800)


def process_image(image_field, instance):
    """Resize an uploaded image, refusing inputs that are too large to process.

    The size and pixel checks run before the expensive decode/resize so a huge
    upload can never force unbounded CPU or memory use.
    """
    if getattr(image_field, "size", 0) > MAX_UPLOAD_BYTES:
        raise ValueError("Image must be 10 MB or smaller.")

    # Rename the image
    new_filename = f"{instance.id}-{instance.name}-{uuid.uuid4()}.jpg"
    image_field.name = new_filename

    try:
        if hasattr(image_field, "seek"):
            image_field.seek(0)
        image = Image.open(image_field)
        width, height = image.size
        if width * height > MAX_IMAGE_PIXELS:
            raise ValueError("Image dimensions are too large.")

        # Convert image to RGB if it's not already (to handle PNG, etc.)
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Resize the image while maintaining the aspect ratio
        image.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)

        # Save the resized image to a BytesIO object
        image_io = io.BytesIO()
        image.save(image_io, format="JPEG")
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
        raise ValueError("Invalid image.") from exc

    image_content = ContentFile(image_io.getvalue(), new_filename)
    return new_filename, image_content
