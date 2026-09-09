import tempfile
import unittest
from pathlib import Path

import autonavy


class ApplicationEntryTests(unittest.TestCase):
    def test_startup_import_failure_becomes_russian_message_and_technical_log(self):
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "launcher.log"
            messages = []

            def failing_loader():
                raise ModuleNotFoundError("missing native runtime")

            exit_code = autonavy.run_application(
                application_loader=failing_loader,
                output=messages.append,
                log_path=log_path,
            )

            log_text = log_path.read_text(encoding="utf-8")

        self.assertEqual(3, exit_code)
        self.assertIn("Не удалось запустить AutoNavy_WT", messages[0])
        self.assertNotIn("missing native runtime", messages[0])
        self.assertIn("missing native runtime", log_text)


if __name__ == "__main__":
    unittest.main()
