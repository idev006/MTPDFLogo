from pathlib import Path

from mtpdflogo.config.rule_preset import is_rule_preset, load_rule_preset, save_rule_preset
from mtpdflogo.domain.models import OverlayType, Position, PositionMode


def test_multi_rule_preset_round_trip_preserves_branch_and_layer_states(tmp_path: Path) -> None:
    path = tmp_path / "rules.toml"
    groups = [
        {
            "id": "amount",
            "name": "จำนวนเงิน",
            "enabled": True,
            "keyword": "จำนวนเงิน",
            "use_regex": False,
            "case_sensitive": False,
            "page_ranges": "1-10",
            "scope": "page",
            "branches": [
                {
                    "id": "three",
                    "name": "เท่ากับ 3",
                    "enabled": False,
                    "is_else": False,
                    "min_occurrences": 3,
                    "max_occurrences": 3,
                    "condition_logic": "any",
                    "conditions": [
                        {
                            "id": "amount-three",
                            "name": "จำนวนเงิน 3 ครั้ง",
                            "enabled": True,
                            "keyword": "จำนวนเงิน",
                            "use_regex": False,
                            "case_sensitive": False,
                            "negate": False,
                            "scope": "page",
                            "min_occurrences": 3,
                            "max_occurrences": 3,
                        },
                        {
                            "id": "approved",
                            "name": "ยังไม่อนุมัติ",
                            "enabled": True,
                            "keyword": "อนุมัติ",
                            "use_regex": False,
                            "case_sensitive": False,
                            "negate": True,
                            "scope": "document",
                            "min_occurrences": 1,
                            "max_occurrences": 1,
                        }
                    ],
                    "overlays": [
                        {
                            "id": "text-a",
                            "name": "Text A",
                            "enabled": False,
                            "type": OverlayType.TEXT,
                            "position_mode": PositionMode.ABSOLUTE,
                            "position": Position.TOP_LEFT,
                            "x_percent": 20.0,
                            "y_percent": 30.0,
                            "text": "อนุมัติ",
                            "font": "Mali-Bold",
                            "font_size": 28,
                            "opacity": 70,
                            "rotation": 5,
                            "color": "#112233",
                            "z_index": 4,
                        }
                    ],
                },
                {
                    "id": "else",
                    "name": "ค่าอื่น",
                    "enabled": True,
                    "is_else": True,
                    "min_occurrences": 0,
                    "max_occurrences": 0,
                    "condition_logic": "all",
                    "conditions": [],
                    "overlays": [],
                },
            ],
        }
    ]

    save_rule_preset(path, groups)
    loaded = load_rule_preset(path)

    assert is_rule_preset(path)
    assert loaded[0]["keyword"] == "จำนวนเงิน"
    assert loaded[0]["branches"][0]["enabled"] is False
    assert loaded[0]["branches"][0]["overlays"][0]["enabled"] is False
    assert loaded[0]["branches"][0]["overlays"][0]["text"] == "อนุมัติ"
    assert loaded[0]["branches"][0]["overlays"][0]["z_index"] == 4
    assert loaded[0]["branches"][0]["conditions"][0]["keyword"] == "จำนวนเงิน"
    assert loaded[0]["branches"][0]["condition_logic"] == "any"
    assert loaded[0]["branches"][0]["conditions"][1]["negate"] is True
    assert loaded[0]["branches"][0]["conditions"][1]["scope"] == "document"
    assert loaded[0]["branches"][1]["is_else"] is True


def test_schema_5_migrates_each_normal_branch_to_one_condition(tmp_path: Path) -> None:
    path = tmp_path / "v5.toml"
    path.write_text(
        "\n".join(
            [
                "schema_version = 5",
                'mode = "multi_rule"',
                "[[rule_groups]]",
                'id = "amount"',
                'name = "Amount"',
                'keyword = "amount"',
                "use_regex = false",
                'scope = "page"',
                "[[rule_groups.branches]]",
                'id = "three"',
                'name = "Equals 3"',
                "min_occurrences = 3",
                "max_occurrences = 3",
            ]
        ),
        encoding="utf-8",
    )

    groups = load_rule_preset(path)
    condition = groups[0]["branches"][0]["conditions"][0]

    assert is_rule_preset(path)
    assert condition["keyword"] == "amount"
    assert condition["min_occurrences"] == condition["max_occurrences"] == 3
