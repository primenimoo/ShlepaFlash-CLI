from sflasher_cli.cache import CacheManager
from sflasher_cli.config import Settings
from sflasher_cli.device_manager import DeviceManager
from sflasher_cli.firmware_manager import FirmwareManager


def test_device_manager_has_known_devices():
    dm = DeviceManager()
    ids = dm.supported_ids()
    assert "plus2" in ids
    assert "s3" in ids
    assert "cardputer" in ids


def test_firmware_manager_filters_by_device(tmp_path, monkeypatch):
    dm = DeviceManager()
    fm = FirmwareManager(dm)
    catalog = {
        "items": [
            {
                "id": "fw1",
                "name": "Bruce",
                "version": "1.0",
                "targets": ["plus2", "s3"],
                "models": {"plus2": {"fileName": "a.bin", "size": 123}},
                "extraFiles": {},
                "extras": {},
            },
            {
                "id": "fw2",
                "name": "Other",
                "version": "1.0",
                "targets": ["cyd"],
                "models": {"cyd": {"fileName": "b.bin", "size": 123}},
                "extraFiles": {},
                "extras": {},
            },
        ]
    }
    fm.load_from_catalog(catalog)
    plus2 = fm.for_device("plus2")
    assert len(plus2) == 1
    assert plus2[0].name == "Bruce"


def test_cache_json(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    cm = CacheManager()
    cm.set_json("test.json", {"a": 1})
    assert cm.get_json("test.json") == {"a": 1}
