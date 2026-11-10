import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("azure_gpu", Path(__file__).resolve().parents[1] / "scripts/azure_gpu.py")
azure_gpu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(azure_gpu)


class AzureGuardTests(unittest.TestCase):
    def test_private_key_and_world_ssh_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            key = Path(temporary) / "key.pub"
            key.write_text("ssh-ed25519 TEST-ONLY-KEY comment")
            with self.assertRaises(ValueError):
                azure_gpu.validate_creation("scene-twin-test", "0.0.0.0/0", key, 2)
            key.write_text("-----BEGIN OPENSSH PRIVATE KEY-----")
            with self.assertRaises(ValueError):
                azure_gpu.validate_creation("scene-twin-test", "8.8.8.8/32", key, 2)

    def test_duration_and_group_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            key = Path(temporary) / "key.pub"
            key.write_text("ssh-ed25519 TEST-ONLY-KEY comment")
            with self.assertRaises(ValueError):
                azure_gpu.validate_creation("another-project", "8.8.8.8/32", key, 2)
            with self.assertRaises(ValueError):
                azure_gpu.validate_creation("scene-twin-test", "8.8.8.8/32", key, 100)

    def test_wrong_tenant_stops_before_provisioning(self):
        identifier = "00000000-0000-0000-0000-000000000001"
        with patch.object(azure_gpu, "az", return_value={"id": identifier, "tenantId": "wrong", "state": "Enabled"}):
            with self.assertRaisesRegex(ValueError, "does not match"):
                azure_gpu.validate_identity(identifier, identifier)

    def test_preflight_does_not_claim_quota_from_command_success(self):
        identifier = "00000000-0000-0000-0000-000000000001"
        calls = [
            {"id": identifier, "tenantId": identifier, "state": "Enabled"},
            [{"name": azure_gpu.SKU, "resourceType": "virtualMachines", "restrictions": []}],
            [{"name": {"value": "standardNCAST4_v3Family"}, "limit": 4, "currentValue": 4}],
        ]
        with patch.object(azure_gpu, "az", side_effect=calls):
            with self.assertRaisesRegex(ValueError, "Fewer than four"):
                azure_gpu.inspect(identifier, identifier)


if __name__ == "__main__":
    unittest.main()
