#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""指标守门器：跑一次评测，断言三项指标不低于基线，低了就 exit 1（给 CI 用）。

用法：
    python check_metrics.py

基线取当前实测值（见 README「结果」）：
    hit@3 76.5% / 拒答 100% / 综合 81.8%
只允许持平或变好 —— 想下调基线，必须在 PR 里说明为什么，而不是偷偷改这个文件。
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
RESULTS = ROOT / "results" / "latest.json"

FLOOR = {
    "hit_at_k": 0.76,          # 实测 76.5%
    "refuse_accuracy": 1.00,   # 实测 100%
    "combined_accuracy": 0.81,  # 实测 81.8%
}
LABEL = {"hit_at_k": "hit@3", "refuse_accuracy": "拒答准确率", "combined_accuracy": "综合准确率"}

print("== 跑评测 ==")
subprocess.run([sys.executable, str(ROOT / "run_eval.py")], check=True, cwd=str(ROOT))

data = json.loads(RESULTS.read_text(encoding="utf-8"))
print("\n== 守门 ==")
failures = []
for key, floor in FLOOR.items():
    got = data[key]
    ok = got + 1e-9 >= floor
    print(f"  {LABEL[key]:<8} {got:>6.1%}   基线 {floor:>6.1%}   {'OK' if ok else 'REGRESSION'}")
    if not ok:
        failures.append((LABEL[key], got, floor))

if failures:
    print("\n指标低于基线，拒绝合并：")
    for name, got, floor in failures:
        print(f"  - {name}: {got:.1%} < {floor:.1%}")
    sys.exit(1)

print("\n全部不低于基线。")
