from uuid import uuid4

from PIL import Image, UnidentifiedImageError
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django_tiptap_editor.views.base_image_upload_view import BaseImageUploadView
from django_tiptap_editor.views.image_upload_error import ImageUploadError


MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
IMAGE_FORMATS = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}


class TipTapImageUploadView(BaseImageUploadView):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required."}, status=401)
        return super().dispatch(request, *args, **kwargs)

    def save(self, file):
        if file.size > MAX_IMAGE_UPLOAD_BYTES:
            raise ImageUploadError("Images must be 10 MB or smaller.")

        try:
            with Image.open(file) as image:
                image_format = image.format
                width, height = image.size
                image.verify()
        except (Image.DecompressionBombError, OSError, UnidentifiedImageError, ValueError) as exc:
            raise ImageUploadError("Upload a valid JPEG, PNG, or WebP image.") from exc

        if image_format not in IMAGE_FORMATS:
            raise ImageUploadError("Upload a valid JPEG, PNG, or WebP image.")
        if width * height > MAX_IMAGE_PIXELS:
            raise ImageUploadError("Image dimensions are too large.")

        file.seek(0)
        path = default_storage.save(
            f"tiptap/{uuid4().hex}{IMAGE_FORMATS[image_format]}",
            file,
        )
        return default_storage.url(path)