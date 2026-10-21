from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.parsers import ConfigParseError, parse_config_text, update_config_text
from backend.service import ApiError, ConfigService, ConflictError, decode_config_bytes
from backend.settings import normalize_launcher_path


class ParserTests(unittest.TestCase):
    def test_toml_preserves_comments_and_updates_value(self):
        text = "# heading\n# The description\nenabled = true # tail\n\n[group]\n# Number here\ncount = 3\n"
        parsed = parse_config_text(text, "toml")
        self.assertEqual(len(parsed["fields"]), 2)
        self.assertIn("The description", parsed["fields"][0]["description"])
        new_text, _ = update_config_text(text, "toml", [{"path": "/enabled", "value": False}])
        self.assertIn("# heading", new_text)
        self.assertIn("# tail", new_text)
        self.assertIn("enabled = false", new_text)
        changed = parse_config_text(new_text, "toml")
        self.assertFalse(changed["fields"][0]["value"])

    def test_toml_multiline_array(self):
        text = "list = [\n  1,\n  2,\n]\n"
        parsed = parse_config_text(text, "toml")
        self.assertEqual(parsed["fields"][0]["value"], [1, 2])
        new_text, _ = update_config_text(text, "toml", [{"path": "/list", "value": [3, 4]}])
        self.assertEqual(parse_config_text(new_text, "toml")["fields"][0]["value"], [3, 4])

    def test_toml_lenient_resource_locations(self):
        text = 'locations = [minecraft:dirt, minecraft:diamond]\n'
        parsed = parse_config_text(text, "toml")
        self.assertEqual(parsed["fields"][0]["value"], ["minecraft:dirt", "minecraft:diamond"])
        self.assertTrue(parsed["fields"][0]["lenient"])
        new_text, _ = update_config_text(text, "toml", [{"path": "/locations", "value": ["minecraft:stone"]}])
        self.assertEqual(parse_config_text(new_text, "toml")["fields"][0]["value"], ["minecraft:stone"])

    def test_json5_comments_and_trailing_comma(self):
        text = '{\n  // first\n  "enabled": true,\n  "nested": {"count": 2,},\n}\n'
        parsed = parse_config_text(text, "json5")
        self.assertEqual(len(parsed["fields"]), 2)
        self.assertEqual(parsed["fields"][0]["description"], "first")
        new_text, _ = update_config_text(text, "json5", [{"path": "/nested/count", "value": 7}])
        self.assertIn('"count":7', new_text.replace(" ", ""))
        self.assertIn("// first", new_text)

    def test_yaml_nested(self):
        text = "# Root description\nroot:\n  # Child switch\n  enabled: true\n  speed: 1.5\n"
        parsed = parse_config_text(text, "yaml")
        self.assertEqual(len(parsed["fields"]), 2)
        self.assertEqual(parsed["fields"][0]["section"], "root")
        self.assertEqual(parsed["fields"][0]["description"], "Child switch")
        self.assertEqual(parsed["fields"][1]["value"], 1.5)
        new_text, _ = update_config_text(text, "yaml", [{"path": "/root/enabled", "value": False}])
        self.assertIn("enabled: false", new_text)

    def test_properties_and_cfg(self):
        text = "# Threads\nthreads=2\n# Flag\nflag=true\n"
        parsed = parse_config_text(text, "properties")
        self.assertEqual(parsed["fields"][0]["value"], 2)
        new_text, _ = update_config_text(text, "properties", [{"path": "/threads", "value": 4}])
        self.assertIn("threads=4", new_text)
        cfg = "# Whether enabled\nEnableScripting=true\nNpcNavRange=32\n"
        parsed_cfg = parse_config_text(cfg, "cfg")
        self.assertEqual(len(parsed_cfg["fields"]), 2)
        new_cfg, _ = update_config_text(cfg, "cfg", [{"path": "/NpcNavRange", "value": 64}])
        self.assertIn("NpcNavRange=64", new_cfg)

    def test_invalid_value_is_rejected(self):
        text = "count = 1\n"
        with self.assertRaises(ConfigParseError):
            update_config_text(text, "toml", [{"path": "/count", "value": "not a number"}])

    def test_large_file_falls_back_to_raw(self):
        text = "x" * 1_600_000
        parsed = parse_config_text(text, "json")
        self.assertTrue(parsed["raw_only"])
        self.assertEqual(parsed["fields"], [])

    def test_mixed_encoding_fallback_preserves_bytes(self):
        data = b"name: test\nnote: \xff\xfe broken\n"
        text, encoding, bom = decode_config_bytes(data)
        self.assertIn(encoding, ("cp1252", "latin-1"))
        self.assertEqual(text.encode(encoding) + bom, data)

    def test_version_folder_normalizes_to_minecraft_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            version = root / "versions" / "Pack"
            version.mkdir(parents=True)
            (version / "mods").mkdir()
            self.assertEqual(normalize_launcher_path(str(version)), root)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.version = self.root / "versions" / "TestPack"
        self.config = self.version / "config"
        self.mods = self.version / "mods"
        self.config.mkdir(parents=True)
        self.mods.mkdir(parents=True)
        version_json = {
            "id": "TestPack",
            "inheritsFrom": "1.20.1",
            "libraries": [{"name": "net.fabricmc:fabric-loader:0.15.0"}],
        }
        (self.version / "TestPack.json").write_text(json.dumps(version_json), encoding="utf-8")
        (self.config / "testmod-common.toml").write_text(
            "# Test boolean\nenabled = true\n# Test number\ncount = 2\n", encoding="utf-8"
        )
        jar_path = self.mods / "testmod-1.0.jar"
        with zipfile.ZipFile(str(jar_path), "w") as archive:
            archive.writestr(
                "fabric.mod.json",
                json.dumps({"schemaVersion": 1, "id": "testmod", "name": "Test Mod", "version": "1.0"}),
            )
        self.service = ConfigService()
        self.patcher = patch("backend.service.current_launcher", return_value=self.root)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp.cleanup()

    def test_discovery_and_association(self):
        versions = self.service.list_versions()
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]["game_version"], "1.20.1")
        self.assertEqual(versions[0]["loader"], "Fabric")
        payload = self.service.mods_payload("TestPack")
        self.assertEqual(payload["stats"]["mods"], 1)
        mod = payload["mods"][0]
        self.assertEqual(mod["config_count"], 1)
        detail = self.service.mod_payload("TestPack", mod["key"])
        self.assertEqual(detail["configs"][0]["field_count"], 2)

    def test_save_structured_and_conflict(self):
        payload = self.service.mods_payload("TestPack")
        key = payload["mods"][0]["key"]
        config = self.service.config_payload("TestPack", key, "testmod-common.toml")
        result = self.service.save_config(
            "TestPack", key, "testmod-common.toml", config["hash"],
            changes=[{"path": "/enabled", "value": False}, {"path": "/count", "value": 5}],
        )
        self.assertTrue(result["ok"])
        text = (self.config / "testmod-common.toml").read_text(encoding="utf-8")
        self.assertIn("enabled = false", text)
        self.assertIn("count = 5", text)
        self.assertIn("# Test boolean", text)
        self.assertTrue(result["backup"])
        self.assertTrue((ROOT / "data" / "backups" / result["backup"]).is_file())
        with self.assertRaises(ConflictError):
            self.service.save_config(
                "TestPack", key, "testmod-common.toml", config["hash"],
                changes=[{"path": "/count", "value": 6}],
            )
        fresh = self.service.config_payload("TestPack", key, "testmod-common.toml")
        self.assertEqual(fresh["fields"][1]["value"], 5)
        self.assertEqual(fresh["hash"], result["hash"])

    def test_raw_save(self):
        payload = self.service.mods_payload("TestPack")
        key = payload["mods"][0]["key"]
        config = self.service.config_payload("TestPack", key, "testmod-common.toml")
        raw = config["raw"].replace("count = 2", "count = 9")
        result = self.service.save_config("TestPack", key, "testmod-common.toml", config["hash"], raw=raw)
        self.assertTrue(result["ok"])
        self.assertEqual(parse_config_text(result["raw"], "toml")["fields"][1]["value"], 9)

    def test_raw_save_preserves_crlf(self):
        target = self.config / "testmod-crlf.properties"
        target.write_bytes(b"name=test\r\ncount=1\r\n")
        payload = self.service.mods_payload("TestPack")
        key = payload["mods"][0]["key"]
        config = self.service.config_payload("TestPack", key, target.name)
        raw = config["raw"].replace("count=1", "count=2")
        self.service.save_config("TestPack", key, target.name, config["hash"], raw=raw)
        data = target.read_bytes()
        self.assertIn(b"\r\n", data)
        self.assertIn(b"count=2\r\n", data)

    def test_path_traversal_rejected(self):
        payload = self.service.mods_payload("TestPack")
        key = payload["mods"][0]["key"]
        with self.assertRaises(ApiError):
            self.service.config_payload("TestPack", key, "../../evil.toml")


if __name__ == "__main__":
    unittest.main()
