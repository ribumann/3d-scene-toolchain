import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.generated_references import (
    Concept, Manifest, contract, generate_references, reference_folder, validate_reference,
)
from scripts.private_gpu_batch import digest


class GeneratedReferenceTests(unittest.TestCase):
    def setUp(self):
        self.concept = Concept(id="pump", category="pump", cases=["I01"], subject="one complete industrial pump")

    def test_hash_and_description_changes_cannot_reuse_a_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = reference_folder(root, self.concept)
            folder.mkdir(parents=True)
            Image.new("RGB", (1024, 1024), "white").save(folder / "reference.png")
            receipt = {"contract": contract(self.concept), "sha256": digest(folder / "reference.png")}
            (folder / "reference.json").write_text(json.dumps(receipt))
            self.assertEqual(validate_reference(folder, self.concept), receipt)
            changed = self.concept.model_copy(update={"subject": "one large slurry pump"})
            self.assertNotEqual(reference_folder(root, changed), folder)
            with self.assertRaisesRegex(ValueError, "contract"):
                validate_reference(folder, changed)
            Image.new("RGB", (1024, 1024), "black").save(folder / "reference.png")
            with self.assertRaisesRegex(ValueError, "hash"):
                validate_reference(folder, self.concept)

    def test_unknown_cases_fail_before_export_or_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            export = root / "export"
            with self.assertRaisesRegex(ValueError, "supported"):
                generate_references(root, root / "absent.json", ["I02"], export)
            self.assertFalse(export.exists())

    def test_duplicate_identity_is_not_an_additional_generation(self):
        value = {"schema_version": 1, "concepts": [self.concept.model_dump()] * 2}
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            Manifest.model_validate(value)
