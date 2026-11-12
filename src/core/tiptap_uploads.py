from datetime import date
from uuid import uuid4

from django.core.cache import cache
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django_tiptap_editor.views.base_image_upload_view import BaseImageUploadView
from django_tiptap_editor.views.image_upload_error import ImageUploadError
from PIL import Image, UnidentifiedImageError

MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
MAX_DAILY_UPLOAD_BYTES = 50 * 1024 * 1024
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

        # Aggregate quota: cap the total bytes a single user can upload per day
        # so repeated uploads cannot exhaust media storage.
        quota_key = f"tiptap-upload-bytes:{self.request.user.pk}:{date.today().isoformat()}"
        cache.add(quota_key, 0, timeout=86400)
        used = cache.get(quota_key, 0)
        if used + file.size > MAX_DAILY_UPLOAD_BYTES:
            raise ImageUploadError("Daily upload quota exceeded.")

        file.seek(0)
        path = default_storage.save(
            f"tiptap/{uuid4().hex}{IMAGE_FORMATS[image_format]}",
            file,
        )
        try:
            cache.incr(quota_key, file.size)
        except ValueError:
            cache.set(quota_key, used + file.size, timeout=86400)
        return default_storage.url(path)
