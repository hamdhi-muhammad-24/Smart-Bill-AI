from pathlib import Path

from app.uploads.watcher import _get_cycle_from_billdate, _resolve_folder_type


def test_shared_cycle_folder_routes_billdate_ranges(tmp_path: Path):
    expected_cycles = {
        **dict.fromkeys(range(1, 4), 1),
        **dict.fromkeys(range(8, 11), 2),
        **dict.fromkeys(range(16, 19), 3),
        **dict.fromkeys(range(24, 27), 4),
    }

    for day, cycle in expected_cycles.items():
        gmf_path = tmp_path / str(day)
        gmf_path.write_text(f"BILLDATE {day:02d}/10/2025|\n", encoding="utf-8")

        assert _get_cycle_from_billdate(gmf_path) == cycle
        assert _resolve_folder_type("Cycle", gmf_path) == f"Cycle_{cycle}"


def test_shared_cycle_folder_routes_unassigned_days_to_no_cycle(tmp_path: Path):
    for day in [4, 5, 6, 7, 11, 12, 13, 14, 15, 19, 20, 21, 22, 23, 27, 28, 29, 30, 31]:
        gmf_path = tmp_path / str(day)
        gmf_path.write_text(f"BILLDATE {day:02d}/10/2025|\n", encoding="utf-8")

        assert _get_cycle_from_billdate(gmf_path) is None
        assert _resolve_folder_type("Cycle", gmf_path) == "No_Cycle"