from katib.core.split import PRESETS, SPLITS, split_from_names


def test_common_folder_names_map_to_a_split() -> None:
    assert split_from_names(["images", "train"]) == "train"
    assert split_from_names(["valid", "images"]) == "val"
    assert split_from_names(["Validation"]) == "val"
    assert split_from_names(["testing"]) == "test"


def test_the_innermost_folder_wins() -> None:
    assert split_from_names(["test", "train"]) == "train"


def test_ordinary_folders_have_no_split() -> None:
    assert split_from_names(["holiday", "2024", "training-notes"]) is None
    assert split_from_names([]) is None


def test_presets_add_up_and_use_known_splits() -> None:
    for ratios in PRESETS.values():
        assert set(ratios) == set(SPLITS)
        assert abs(sum(ratios.values()) - 1) < 1e-9
