"""Strict public resource-text catalogue regressions."""

import json
from pathlib import Path
import shutil

import pytest

from multi_agent_personalities.case_catalog import default_case_catalog_directory, load_case_catalog
from multi_agent_personalities.resource_text_catalog import default_resource_text_directory, load_resource_text_catalog


ROOT = Path(__file__).resolve().parents[1]
CASES = load_case_catalog(default_case_catalog_directory(ROOT))
RESOURCE_ROOT = default_resource_text_directory(ROOT)
CATALOG = load_resource_text_catalog(RESOURCE_ROOT, CASES)


def copied_catalogue(tmp_path: Path) -> Path:
    target = tmp_path / "resources_text"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(RESOURCE_ROOT, target)
    return target


def test_verified_resources_and_player_only_images_are_exactly_classified() -> None:
    readable = {resource.resource_id for resource in CATALOG.resources if resource.agent_readable}
    player_only = {resource.resource_id for resource in CATALOG.resources if not resource.agent_readable}
    assert readable == {
        "demo-1-vanishing-from-hyde-park-directory",
        "demo-1-vanishing-from-hyde-park-informants",
        "demo-1-vanishing-from-hyde-park-newspaper",
        "demo-2-an-irregular-meeting-directory",
        "demo-2-an-irregular-meeting-informants",
        "demo-2-an-irregular-meeting-newspaper",
    }
    assert player_only == {
        "demo-1-vanishing-from-hyde-park-map",
        "demo-2-an-irregular-meeting-map",
        "demo-3-the-disappearance-of-a-student-floor-plans",
    }
    assert all(not resource.entries for resource in CATALOG.resources if not resource.agent_readable)


def test_verified_structured_entries_and_tracker_exclusion() -> None:
    demo1 = CATALOG.get("demo-1-vanishing-from-hyde-park", "demo-1-vanishing-from-hyde-park-directory")
    assert [entry.texts["en"] for entry in demo1.entries][:3] == [
        "Hennessy, Patrick — 37 WC", "Grosvenor Investments — 32 NW", "Nance, Yvonne — 32 NW",
    ]
    informants = CATALOG.get("demo-2-an-irregular-meeting", "demo-2-an-irregular-meeting-informants")
    assert len(informants.entries) == 2
    assert {entry.entry_id for entry in informants.entries} == {"national-archives", "scotland-yard"}
    assert "Circle these letters" not in informants.render()


def test_loader_never_opens_private_conclusion_files(monkeypatch: pytest.MonkeyPatch) -> None:
    original = Path.read_text
    opened: list[Path] = []
    def spy(path: Path, *args, **kwargs):
        opened.append(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", spy)
    load_resource_text_catalog(RESOURCE_ROOT, CASES)
    assert opened and all("/conclusions/private/" not in str(path) for path in opened)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda data: data.update(case_id="demo-2-an-irregular-meeting"), "cross-directory"),
        (lambda data: data.update(resource_type="map"), "type does not match"),
        (lambda data: data.update(source_asset_path="../escape.png"), "safe local relative"),
        (lambda data: data["entries"].append(data["entries"][0]), "duplicate resource text"),
    ),
)
def test_invalid_cross_file_definitions_fail_loudly(tmp_path: Path, mutation, message: str) -> None:
    root = copied_catalogue(tmp_path)
    path = root / "demo-1-vanishing-from-hyde-park" / "directory.json"
    data = json.loads(path.read_text()); mutation(data); path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match=message):
        load_resource_text_catalog(root, CASES, asset_root=ROOT / "configs" / "investigation")


def test_missing_and_duplicate_resource_definitions_fail_loudly(tmp_path: Path) -> None:
    root = copied_catalogue(tmp_path)
    (root / "demo-1-vanishing-from-hyde-park" / "directory.json").unlink()
    with pytest.raises(ValueError, match="missing"):
        load_resource_text_catalog(root, CASES, asset_root=ROOT / "configs" / "investigation")


def test_removing_complete_r1_case_directory_fails_loudly(tmp_path: Path) -> None:
    root = copied_catalogue(tmp_path)
    shutil.rmtree(root / "demo-1-vanishing-from-hyde-park")
    with pytest.raises(ValueError, match="case IDs must agree"):
        load_resource_text_catalog(root, CASES, asset_root=ROOT / "configs" / "investigation")
    root = copied_catalogue(tmp_path / "again")
    original = root / "demo-1-vanishing-from-hyde-park" / "directory.json"
    shutil.copyfile(original, original.with_name("duplicate.json"))
    with pytest.raises(ValueError, match="duplicate resource text resource_id"):
        load_resource_text_catalog(root, CASES, asset_root=ROOT / "configs" / "investigation")


def test_guidance_is_public_concise_and_case_complete() -> None:
    assert [case.case_id for case in CATALOG.guidance] == [
        "demo-1-vanishing-from-hyde-park",
        "demo-2-an-irregular-meeting",
        "demo-3-the-disappearance-of-a-student",
    ]
    rendered = " ".join(entry.texts["en"] for case in CATALOG.guidance for entry in case.entries)
    assert "initial lead budget is 10" in rendered
    assert "A, B or C only when" in rendered
    assert "32 NW" in rendered
