import shutil
import tempfile
import unittest
from pathlib import Path

from toolkit.resources import read_image


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class UnicodeResourceTests(unittest.TestCase):
    def test_reads_png_from_windows_path_containing_cyrillic(self):
        with tempfile.TemporaryDirectory(prefix="Ресурсы AutoNavy ") as directory:
            target = Path(directory) / "изображение.png"
            shutil.copy2(PROJECT_ROOT / "src" / "origin_map.png", target)

            image = read_image(target)

        self.assertIsNotNone(image)
        self.assertEqual((2048, 2048, 3), image.shape)


if __name__ == "__main__":
    unittest.main()
