from pathlib import Path

from generate_samples import generate_all


def test_sample_generation(tmp_path: Path) -> None:
    paths = generate_all(tmp_path)
    assert paths["medicine"].exists()
    assert paths["bill"].exists()
    assert paths["medicine"].stat().st_size > 1000
