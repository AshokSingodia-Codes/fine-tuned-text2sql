"""Unit test ensuring Google Colab notebook contains no mock backend calls."""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_notebook_has_no_mock_backend():
    for nb_name in ["run_phase1_colab.ipynb", "run_phase1_kaggle.ipynb"]:
        nb_path = PROJECT_ROOT / "notebooks" / nb_name
        assert nb_path.exists(), f"notebooks/{nb_name} must exist."

        with open(nb_path, "r", encoding="utf-8") as f:
            nb_data = json.load(f)

        for i, cell in enumerate(nb_data.get("cells", [])):
            if cell.get("cell_type") == "code":
                src_lines = cell.get("source", [])
                src_text = "".join(src_lines)
                assert "--backend mock" not in src_text, (
                    f"{nb_name} Cell {i} contains '--backend mock' argument, which is prohibited in Phase 1."
                )
                assert "MockBackend" not in src_text, (
                    f"{nb_name} Cell {i} references MockBackend, which is prohibited in Phase 1."
                )
