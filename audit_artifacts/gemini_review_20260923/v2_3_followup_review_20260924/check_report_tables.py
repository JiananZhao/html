"""Compare submitted report numbers with submitted CSVs, without editing them."""
import json
import re
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent
SUB = OUT.parent / "v2_3_remediation"
columns = ["Strat_Final", "Strat_XIRR%", "Strat_MDD%", "Bench_Final",
           "Bench_XIRR%", "Alpha_XIRR%", "Stop_Loss_Orders"]
checks = []
asset = None
for line in (SUB / "REMEDIATION_REPORT_v2_3.md").read_text(encoding="utf-8").splitlines():
    heading = re.match(r"### [123]\. (NOW|QQQ|SPY) 标的", line)
    if heading:
        asset = heading.group(1)
    if line.startswith("| **C"):
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        config = int(cells[0].replace("*", "")[1:])
        csv = pd.read_csv(SUB / f"factorial_ablation_results_v2_3_{asset.lower()}.csv")
        for cell, column in zip(cells[2:], columns):
            reported = float(cell.replace("*", "").replace(",", "").replace("%", ""))
            actual = float(csv.iloc[config][column])
            assert abs(reported - actual) < 1e-8, (asset, config, column, reported, actual)
            checks.append({"asset": asset, "config": config, "column": column, "value": actual})
assert len(checks) == 168
(OUT / "report_table_checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
print("REPORT_TABLES_MATCH: 24 rows, 168 numeric cells")
