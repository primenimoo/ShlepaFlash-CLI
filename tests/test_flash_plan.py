from pathlib import Path
from sflasher_cli.flash_engine import plan_single_bin, looks_like_merged_image


def test_app_image_defaults_to_0x10000(tmp_path: Path):
    p = tmp_path / "app.bin"
    # minimal ESP image magic + padding
    data = bytearray(0x200)
    data[0] = 0xE9
    data[1] = 0x02
    p.write_bytes(data)
    plan = plan_single_bin(p, "plus2")
    assert plan[0].offset == 0x10000


def test_merged_image_detected(tmp_path: Path):
    p = tmp_path / "merged.bin"
    data = bytearray(0x9002)
    data[0] = 0xE9
    data[0x8000] = 0xAA
    data[0x8001] = 0x50
    p.write_bytes(data)
    assert looks_like_merged_image(bytes(data))
    plan = plan_single_bin(p, "plus2")
    assert plan[0].offset == 0x0
