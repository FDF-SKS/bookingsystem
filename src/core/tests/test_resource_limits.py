"""Regression tests for resource-exhaustion guards."""
import io
import shutil
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from organization.models import Volunteer
from Sjak.forms import SjakItemForm
from utils.image_utils import MAX_UPLOAD_BYTES


def _png(name="image.png", size=(20, 20)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "red").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class VolunteerImageCleanupTests(TestCase):
    def test_replacing_image_deletes_old_files(self):
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, True)

        with override_settings(MEDIA_ROOT=media_root):
            user = Volunteer.objects.create_user(
                username="img-user",
                email="img@example.com",
                password="pw-12345-xyz",
            )
            user.image = _png("old.png")
            user.save()

            old_image = Path(user.image.path)
            old_thumb = Path(user.image_thumbnail.path)
            self.assertTrue(old_image.exists())
            self.assertTrue(old_thumb.exists())

            user.image = _png("new.png")
            user.save()

            self.assertFalse(old_image.exists())
            self.assertFalse(old_thumb.exists())
            self.assertTrue(Path(user.image.path).exists())
            self.assertTrue(Path(user.image_thumbnail.path).exists())


class SjakImageValidationTests(TestCase):
    def test_oversized_image_is_rejected(self):
        upload = _png()
        upload.size = MAX_UPLOAD_BYTES + 1

        form = SjakItemForm(data={"name": "Stor"}, files={"image": upload})

        self.assertFalse(form.is_valid())
        self.assertIn("image", form.errors)

    def test_valid_image_is_accepted(self):
        form = SjakItemForm(data={"name": "Lille"}, files={"image": _png()})

        self.assertTrue(form.is_valid(), form.errors)
