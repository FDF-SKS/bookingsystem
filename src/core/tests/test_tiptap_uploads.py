from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.tiptap_uploads import MAX_IMAGE_UPLOAD_BYTES


class TipTapImageUploadTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="editor",
            email="editor@example.com",
            password="test-password",
        )
        self.client.force_login(user)

    @staticmethod
    def make_png():
        image_data = BytesIO()
        Image.new("RGB", (3, 3), color="orange").save(image_data, format="PNG")
        return SimpleUploadedFile("photo.png", image_data.getvalue(), content_type="image/png")

    def test_authenticated_user_can_upload_valid_image(self):
        with TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse("tiptap_image_upload"),
                {"file": self.make_png()},
            )

            self.assertEqual(response.status_code, 200)
            image_url = response.json()["location"]
            self.assertTrue(image_url.startswith("/media/tiptap/"))
            self.assertTrue(image_url.endswith(".png"))

    def test_rejects_non_image_upload(self):
        response = self.client.post(
            reverse("tiptap_image_upload"),
            {"file": SimpleUploadedFile("photo.png", b"not an image", content_type="image/png")},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("valid JPEG", response.json()["error"])

    def test_rejects_oversized_upload(self):
        upload = SimpleUploadedFile(
            "large.png",
            b"x" * (MAX_IMAGE_UPLOAD_BYTES + 1),
            content_type="image/png",
        )
        response = self.client.post(reverse("tiptap_image_upload"), {"file": upload})

        self.assertEqual(response.status_code, 400)
        self.assertIn("10 MB", response.json()["error"])

    def test_requires_authentication(self):
        self.client.logout()
        response = self.client.post(
            reverse("tiptap_image_upload"),
            {"file": self.make_png()},
        )

        self.assertEqual(response.status_code, 401)