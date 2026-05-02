import unittest
from unittest.mock import patch, MagicMock
import subprocess
from immich_ingest import ImmichIngestor

class TestImmichIngestor(unittest.TestCase):
    def setUp(self):
        self.ingestor = ImmichIngestor(
            api_url="http://example.com",
            api_key="test_key",
            photos_root="/tmp/photos",
            dry_run=True
        )

    @patch("subprocess.run")
    def test_verify_connectivity_success(self, mock_run):
        # Mock successful execution
        mock_run.return_value = MagicMock(returncode=0)

        result = self.ingestor.verify_connectivity()

        self.assertTrue(result)
        mock_run.assert_called_once_with(["immich-go", "-h"], capture_output=True, check=True)

    @patch("subprocess.run")
    def test_verify_connectivity_file_not_found(self, mock_run):
        # Mock FileNotFoundError
        mock_run.side_effect = FileNotFoundError("No such file or directory")

        result = self.ingestor.verify_connectivity()

        self.assertFalse(result)
        mock_run.assert_called_once_with(["immich-go", "-h"], capture_output=True, check=True)

    @patch("subprocess.run")
    def test_verify_connectivity_called_process_error(self, mock_run):
        # Mock subprocess.CalledProcessError
        mock_run.side_effect = subprocess.CalledProcessError(1, ["immich-go", "-h"])

        result = self.ingestor.verify_connectivity()

        self.assertFalse(result)
        mock_run.assert_called_once_with(["immich-go", "-h"], capture_output=True, check=True)

if __name__ == "__main__":
    unittest.main()
