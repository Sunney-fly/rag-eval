#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rag-eval · 一个 RAG 检索层的可复现评测

用法：
    python run_eval.py                 # 跑全部用例，输出指标 + results/latest.json
    python run_eval.py --sweep         # 扫拒答阈值，输出「召回 vs 拒答」权衡表
    python run_eval.py --calibrate     # 只打每条用例的 top-1 分数，用于看分布
    python run_eval.py --topk 5        # 改检索深度

设计要点
--------
1. 纯标准库，零依赖。BM25 手写，没有引入任何检索框架。
2. 中文用「字符 bigram」分词，英文/数字按词切，不依赖 jieba 等外部分词器。
3. 检索单位是「章节块」（按 #/##/### 切），不是整篇文档 —— 这才是 RAG 的真实粒度，
   否则一篇文档一个向量，hit@3 恒等于 1，指标没有意义。
4. 拒答组单独评估：检索最高分低于阈值才判「查不到」。阈值不是拍的，
   由 --sweep 扫出来，README 里给完整权衡表。
"""

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "corpus"
CASES = ROOT / "cases.jsonl"
RESULTS = ROOT / "results"

# BM25 参数：k1 控制词频饱和，b 控制长度归一化强度。1.5 / 0.75 是常用经验值。
K1 = 1.5
B = 0.75

# 默认拒答阈值。取 --sweep 里综合准确率最高的那个（见 README「阈值怎么定的」）。
DEFAULT_REFUSE_THRESHOLD = 6.0


# ─────────────────────────────────────────────────────────────
# 1. 语料加载：按标题切块
# ─────────────────────────────────────────────────────────────
def load_chunks(corpus_dir: Path):
    """把每篇 markdown 按 #/##/### 切成「章节块」。

    返回 [{"doc": 文件名, "section": 标题, "text": 正文}]
    """
    chunks = []
    for path in sorted(corpus_dir.glob("*.md")):
        doc = path.name
        raw = path.read_text(encoding="utf-8", errors="replace")
        cur_heading, buf = "（篇首）", []
        for line in raw.splitlines():
            if re.match(r"^#{1,3}\s+", line):
                body = "\n".join(buf).strip()
                if body:
                    chunks.append({"doc": doc, "section": cur_heading, "text": body})
                cur_heading = re.sub(r"^#{1,3}\s+", "", line).strip()
                buf = []
            else:
                buf.append(line)
        body = "\n".join(buf).strip()
        if body:
            chunks.append({"doc": doc, "section": cur_heading, "text": body})
    return chunks


# ─────────────────────────────────────────────────────────────
# 2. 分词：中文 bigram + 英文词
# ─────────────────────────────────────────────────────────────
def tokenize(text: str):
    """中文按字符 bigram 切，英文/数字/下划线按词切。

    为什么中文用 bigram 而不是单字：
      单字区分度太低（「的」「是」遍地都是），bigram 已能表达「新增工具」这类双字词，
      且不需要外部词典。纯标准库条件下这是性价比最高的方案。
    """
    text = text.lower()
    tokens = re.findall(r"[a-z0-9_]+", text)
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    return tokens


# ─────────────────────────────────────────────────────────────
# 3. BM25
# ─────────────────────────────────────────────────────────────
class BM25Index:
    def __init__(self, docs_tokens):
        self.n = len(docs_tokens)
        self.doc_len = [len(t) for t in docs_tokens]
        self.avgdl = sum(self.doc_len) / self.n if self.n else 0
        self.postings = {}
        for i, toks in enumerate(docs_tokens):
            for t in toks:
                self.postings.setdefault(t, {})
                self.postings[t][i] = self.postings[t].get(i, 0) + 1

    def idf(self, token):
        n_qi = len(self.postings.get(token, {}))
        if n_qi == 0:
            return 0.0
        return math.log(1 + (self.n - n_qi + 0.5) / (n_qi + 0.5))

    def score(self, query_tokens, idx):
        dl = self.doc_len[idx] or 1
        s = 0.0
        for t in query_tokens:
            f = self.postings.get(t, {}).get(idx, 0)
            if f == 0:
                continue
            s += self.idf(t) * (f * (K1 + 1)) / (f + K1 * (1 - B + B * dl / self.avgdl))
        return s

    def search(self, query: str, top_k: int = 3):
        qt = tokenize(query)
        scored = sorted(((self.score(qt, i), i) for i in range(self.n)), reverse=True)
        return scored[:top_k]


# ─────────────────────────────────────────────────────────────
# 4. 评测
# ─────────────────────────────────────────────────────────────
def load_cases():
    if not CASES.exists():
        sys.exit(f"缺少用例文件：{CASES}")
    cases = []
    for line in CASES.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            cases.append(json.loads(line))
    return cases


def collect(index, chunks, cases, top_k):
    """跑一遍所有用例，记录与阈值无关的事实：top-k 结果、top1 分数、是否命中。"""
    rows = []
    for case in cases:
        t0 = time.perf_counter()
        hits = index.search(case["q"], top_k=top_k)
        ms = (time.perf_counter() - t0) * 1000

        top = [{"doc": chunks[i]["doc"], "section": chunks[i]["section"], "score": round(s, 4)}
               for s, i in hits]
        row = {"id": case["id"], "group": case["group"], "q": case["q"],
               "top": top, "score": top[0]["score"], "ms": round(ms, 3)}

        if case["group"] == "refuse":
            row["hit"] = None                       # 拒答组不看命中，只看分数
            row["expect"] = "score < 阈值"
        else:
            expect = set(case["expect_docs"])
            row["hit"] = bool(expect & {t["doc"] for t in top})
            row["expect"] = sorted(expect)
        rows.append(row)
    return rows


def summarize(rows, threshold):
    """统计给定阈值下的通过数。

    ⚠ 关键：真问题的判定必须同时满足「命中期望文档」和「分数达到阈值」。
      只判命中是错的 —— 分数低于阈值时，系统实际会回答「查不到」，等于漏召回。
      （这一条是写扫描表时发现的：最初漏了，导致 hit@k 不随阈值变化，明显不合常理。）
    """
    rec_total = sum(1 for r in rows if r["group"] != "refuse")
    rec_ok = sum(1 for r in rows
                 if r["group"] != "refuse" and r["hit"] and r["score"] >= threshold)
    ref_total = sum(1 for r in rows if r["group"] == "refuse")
    ref_ok = sum(1 for r in rows if r["group"] == "refuse" and r["score"] < threshold)
    return rec_ok, rec_total, ref_ok, ref_total


def report(rows, threshold, top_k, idx):
    rec_ok, rec_total, ref_ok, ref_total = summarize(rows, threshold)
    hit_rate = rec_ok / rec_total if rec_total else 0
    ref_rate = ref_ok / ref_total if ref_total else 0
    total_ok, total = rec_ok + ref_ok, rec_total + ref_total

    lat = sorted(r["ms"] for r in rows)
    p50 = lat[len(lat) // 2] if lat else 0

    print(f"\n{'='*66}")
    print(f"语料    {idx['docs']} 篇 → {idx['chunks']} 个检索块")
    print(f"用例    {total} 条（召回 {rec_total} / 拒答 {ref_total}）")
    print(f"参数    k1={K1}  b={B}  top_k={top_k}  拒答阈值={threshold}")
    print(f"{'='*66}")
    print(f"hit@{top_k}          {rec_ok}/{rec_total} = {hit_rate:>6.1%}")
    print(f"拒答准确率       {ref_ok}/{ref_total} = {ref_rate:>6.1%}")
    print(f"综合准确率       {total_ok}/{total} = {total_ok/total:>6.1%}")
    print(f"检索延迟 p50     {p50:.1f} ms")
    print(f"{'='*66}")

    fails = [r for r in rows if (r["group"] == "refuse" and r["score"] >= threshold)
             or (r["group"] != "refuse" and not r["hit"])]
    if fails:
        print("\n未通过：")
        for r in fails:
            why = (f"分数 {r['score']:.2f} ≥ 阈值" if r["group"] == "refuse"
                   else f"期望 {r['expect']}，实得 {r['top'][0]['doc']}({r['top'][0]['score']:.2f})")
            print(f"  [{r['id']}] {r['q'][:32]:<34} {why}")

    RESULTS.mkdir(exist_ok=True)
    out = {
        "corpus_docs": idx["docs"], "chunks": idx["chunks"], "cases": total,
        "hit_at_k": round(hit_rate, 4), "refuse_accuracy": round(ref_rate, 4),
        "combined_accuracy": round(total_ok / total, 4),
        "latency_p50_ms": round(p50, 2),
        "k1": K1, "b": B, "top_k": top_k, "refuse_threshold": threshold,
        "detail": rows,
    }
    (RESULTS / "latest.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果写入 {RESULTS / 'latest.json'}")


def sweep(rows, top_k):
    """扫拒答阈值，把「召回 vs 拒答」的权衡整体摊开，而不是只报一个点。"""
    print(f"\n{'='*66}")
    print("阈值扫描：单一阈值切不开的 trade-off")
    print(f"{'='*66}")
    print(f"{'阈值':>6}  {'hit@'+str(top_k):>8}  {'拒答':>8}  {'综合':>8}")
    print("-" * 66)
    best = (None, -1)
    for i in range(6, 41):
        th = i / 4.0                       # 1.5 .. 10.0，步长 0.25
        ro, rt, fo, ft = summarize(rows, th)
        comb = (ro + fo) / (rt + ft)
        mark = ""
        if comb > best[1]:
            best = (th, comb)
            mark = "  ←"
        if i % 2 == 0:                     # 隔行打印，避免太密
            print(f"{th:>6.2f}  {ro/rt:>7.1%}  {fo/ft:>7.1%}  {comb:>7.1%}{mark}")
    print("-" * 66)
    print(f"综合准确率最高：阈值 {best[0]:.2f} → {best[1]:.1%}")
    print("\n说明：召回率不随阈值变化（召回只看 hit@k），变的是「有多少真问题被误判成查不到」。")
    print("      阈值越高，拒答越准，但真问题被误拒的也越多。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true", help="扫拒答阈值")
    ap.add_argument("--calibrate", action="store_true", help="只打每条用例 top-1 分数")
    ap.add_argument("--topk", type=int, default=3)
    ap.add_argument("--threshold", type=float, default=DEFAULT_REFUSE_THRESHOLD)
    args = ap.parse_args()

    chunks = load_chunks(CORPUS)
    if not chunks:
        sys.exit(f"语料为空，检查 {CORPUS}")
    index = BM25Index([tokenize(c["text"]) for c in chunks])
    idx = {"docs": len(list(CORPUS.glob("*.md"))), "chunks": len(chunks)}
    cases = load_cases()
    rows = collect(index, chunks, cases, args.topk)

    if args.calibrate:
        print(f"\n{'id':<6}{'组':<8}{'top1分':>9}  top1 文档")
        for r in rows:
            print(f"{r['id']:<6}{r['group']:<8}{r['score']:>9.3f}  {r['top'][0]['doc']}")
        pos = [r["score"] for r in rows if r["group"] != "refuse"]
        neg = [r["score"] for r in rows if r["group"] == "refuse"]
        print(f"\n正例 top1：min={min(pos):.2f}  median={sorted(pos)[len(pos)//2]:.2f}  max={max(pos):.2f}")
        print(f"拒答 top1：min={min(neg):.2f}  median={sorted(neg)[len(neg)//2]:.2f}  max={max(neg):.2f}")
        print(f"重叠区间：{max(min(pos), min(neg)):.2f} ~ {min(max(pos), max(neg)):.2f}  ← 单一阈值切不开的原因")
    elif args.sweep:
        sweep(rows, args.topk)
    else:
        report(rows, args.threshold, args.topk, idx)


if __name__ == "__main__":
    main()
