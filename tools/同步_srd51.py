#!/usr/bin/env python3
"""同步 D&D 5e（2014）SRD 5.1 结构化内容库。

数据结构来源：5e-bits/5e-database 的 2014 英文 SRD 数据。
规则权威来源：Wizards of the Coast《System Reference Document 5.1》CC BY 4.0。

脚本只生成机器检索用 JSON 条目和 Markdown 索引，不改写 01_核心规则。
"""

from __future__ import annotations

import json
import re
import shutil
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "02_规则内容库"
ENTRY_ROOT = OUT / "条目"
INDEX_ROOT = OUT / "索引"

BASE_URL = "https://raw.githubusercontent.com/5e-bits/5e-database/refs/heads/main/src/2014/en"
OFFICIAL_SRD_URL = "https://media.wizards.com/2023/downloads/dnd/SRD_CC_v5.1.pdf"
DATABASE_URL = "https://github.com/5e-bits/5e-database"

SOURCES: dict[str, tuple[str, str]] = {
    "ability-scores": ("能力值", "5e-SRD-Ability-Scores.json"),
    "alignments": ("阵营", "5e-SRD-Alignments.json"),
    "backgrounds": ("背景", "5e-SRD-Backgrounds.json"),
    "classes": ("职业", "5e-SRD-Classes.json"),
    "conditions": ("状态", "5e-SRD-Conditions.json"),
    "damage-types": ("伤害类型", "5e-SRD-Damage-Types.json"),
    "equipment-categories": ("装备类别", "5e-SRD-Equipment-Categories.json"),
    "equipment": ("装备", "5e-SRD-Equipment.json"),
    "feats": ("专长", "5e-SRD-Feats.json"),
    "features": ("职业特性", "5e-SRD-Features.json"),
    "languages": ("语言", "5e-SRD-Languages.json"),
    "levels": ("职业等级", "5e-SRD-Levels.json"),
    "magic-items": ("魔法物品", "5e-SRD-Magic-Items.json"),
    "magic-schools": ("法术学派", "5e-SRD-Magic-Schools.json"),
    "monsters": ("怪物", "5e-SRD-Monsters.json"),
    "proficiencies": ("熟练", "5e-SRD-Proficiencies.json"),
    "races": ("种族", "5e-SRD-Races.json"),
    "rule-sections": ("规则章节", "5e-SRD-Rule-Sections.json"),
    "rules": ("规则原文索引", "5e-SRD-Rules.json"),
    "skills": ("技能", "5e-SRD-Skills.json"),
    "spells": ("法术", "5e-SRD-Spells.json"),
    "subclasses": ("子职业", "5e-SRD-Subclasses.json"),
    "subraces": ("亚种", "5e-SRD-Subraces.json"),
    "traits": ("种族特性", "5e-SRD-Traits.json"),
    "weapon-properties": ("武器属性", "5e-SRD-Weapon-Properties.json"),
}


def fetch_json(filename: str) -> Any:
    url = f"{BASE_URL}/{filename}"
    request = urllib.request.Request(url, headers={"User-Agent": "gainianjilu-srd-sync/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def safe_slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = value.strip("-.")
    return value or "entry"


def entry_id(item: dict[str, Any], position: int) -> str:
    if item.get("index"):
        return safe_slug(str(item["index"]))
    if item.get("name"):
        return safe_slug(str(item["name"]))
    return f"entry-{position:04d}"


def entry_name(item: dict[str, Any], fallback: str) -> str:
    if item.get("name"):
        return str(item["name"])
    if item.get("index"):
        return str(item["index"])
    return fallback


def normalize_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        if isinstance(data.get("results"), list):
            return [item for item in data["results"] if isinstance(item, dict)]
        return [data]
    raise TypeError(f"不支持的数据结构：{type(data).__name__}")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_category_index(category_key: str, display_name: str, records: list[dict[str, str]], filename: str) -> None:
    lines = [
        f"# {display_name}索引",
        "",
        f"- 条目数：{len(records)}",
        f"- 结构化来源：`{filename}`",
        "- 条目正文保持英文原始数据，以避免翻译改变规则数值；对外输出时可翻译，但结算以原字段为准。",
        "",
        "## 条目",
        "",
    ]
    for record in sorted(records, key=lambda r: (r["name"].lower(), r["id"])):
        lines.append(f"- [{record['name']}](../条目/{category_key}/{record['id']}.json)")
    (INDEX_ROOT / f"{category_key}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if ENTRY_ROOT.exists():
        shutil.rmtree(ENTRY_ROOT)
    if INDEX_ROOT.exists():
        shutil.rmtree(INDEX_ROOT)
    ENTRY_ROOT.mkdir(parents=True, exist_ok=True)
    INDEX_ROOT.mkdir(parents=True, exist_ok=True)

    manifest: dict[str, Any] = {
        "ruleset": "D&D 5e (2014)",
        "baseline": "SRD 5.1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "official_srd": OFFICIAL_SRD_URL,
        "structured_data_source": DATABASE_URL,
        "categories": {},
    }

    total = 0
    overview = [
        "# SRD 5.1 内容数据库索引",
        "",
        "本目录保存按条目拆分的机器可读内容。不要递归读取全部条目；先读取本索引，再只读取当前角色、法术、怪物、物品或规则所需条目。",
        "",
        "结构化条目以英文原始字段保存，避免翻译误改数值、触发条件和例外。中文规则说明位于 `01_核心规则`。",
        "",
        "## 分类",
        "",
    ]

    for category_key, (display_name, filename) in SOURCES.items():
        data = fetch_json(filename)
        items = normalize_items(data)
        category_dir = ENTRY_ROOT / category_key
        category_dir.mkdir(parents=True, exist_ok=True)
        records: list[dict[str, str]] = []

        for position, item in enumerate(items, start=1):
            item_id = entry_id(item, position)
            name = entry_name(item, item_id)
            write_json(category_dir / f"{item_id}.json", item)
            records.append({"id": item_id, "name": name})

        write_category_index(category_key, display_name, records, filename)
        manifest["categories"][category_key] = {
            "display_name": display_name,
            "source_file": filename,
            "count": len(records),
            "index": f"索引/{category_key}.md",
            "entry_directory": f"条目/{category_key}",
        }
        total += len(records)
        overview.append(f"- [{display_name}](索引/{category_key}.md)：{len(records)} 条")

    manifest["total_entries"] = total
    write_json(OUT / "manifest.json", manifest)
    (OUT / "README.md").write_text("\n".join(overview) + "\n", encoding="utf-8")
    print(f"已生成 {len(SOURCES)} 个分类，共 {total} 个条目。")


if __name__ == "__main__":
    main()
