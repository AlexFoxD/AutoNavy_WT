import unittest
from pathlib import Path

from toolkit import process_path


class ProjectPathTests(unittest.TestCase):
    def test_path_file_is_anchored_to_repository_root(self):
        expected = Path(process_path.__file__).resolve().parents[1] / "path.json"

        self.assertEqual(expected, process_path.PATH_FILE)


if __name__ == "__main__":
    unittest.main()
