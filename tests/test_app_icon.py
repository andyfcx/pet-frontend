import unittest
from unittest.mock import patch

from biometeo_frontend import main


class FakeRoot:
    def iconphoto(self, default: bool, image: object) -> None:
        self.iconphoto_args = (default, image)


class AppIconTests(unittest.TestCase):
    def test_packaged_icon_exists(self) -> None:
        self.assertTrue(main.APP_ICON_PATH.is_file())

    def test_apply_app_icon_keeps_image_alive(self) -> None:
        root = FakeRoot()
        image = object()

        with patch.object(main, "PhotoImage", return_value=image) as photo_image:
            self.assertTrue(main.apply_app_icon(root))

        photo_image.assert_called_once_with(file=str(main.APP_ICON_PATH))
        self.assertEqual(root.iconphoto_args, (True, image))
        self.assertIs(root._biometeo_icon_image, image)

    def test_apply_app_icon_does_not_block_startup_on_error(self) -> None:
        with patch.object(main, "PhotoImage", side_effect=RuntimeError("no display")):
            self.assertFalse(main.apply_app_icon(FakeRoot()))


if __name__ == "__main__":
    unittest.main()
