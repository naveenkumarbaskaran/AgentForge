#!/usr/bin/env python3
"""Simulated AgentForge demo for terminal recording."""
import time, sys

def c(code, text):
    return f"\033[{code}m{text}\033[0m"

def slow(text, delay=0.01):
    for ch in text:
        sys.stdout.write(ch); sys.stdout.flush(); time.sleep(delay)
    print()

def section(text):
    print(c("1;36", f"\n{'─'*60}"))
    print(c("1;36", f"  {text}"))
    print(c("1;36", f"{'─'*60}"))

print(c("1;35", """
   █████╗  ██████╗ ███████╗███╗   ██╗████████╗
  ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
  ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
  ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║
  ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝
  ███████╗ ██████╗ ██████╗  ██████╗ ███████╗
  ██╔════╝██╔═══██╗██╔══██╗██╔════╝ ██╔════╝
  █████╗  ██║   ██║██████╔╝██║  ███╗█████╗
  ██╔══╝  ██║   ██║██╔══██╗██║   ██║██╔══╝
  ██║     ╚██████╔╝██║  ██║╚██████╔╝███████╗
  ╚═╝      ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝"""))

time.sleep(0.3)
print(c("2", "  v0.1.0 • Production-Grade Enterprise AI Agent Framework"))
time.sleep(0.5)

section("1 · INITIALIZING PEOS PIPELINE")
time.sleep(0.2)

steps = [
    ("Planner",     "IntentCascade loaded  (4 patterns)"),
    ("Executor",    "DynamicToolBinder ready (3 tool groups, 7 tools)"),
    ("Observer",    "QualityGate thresholds set (confidence≥0.85)"),
    ("Synthesiser", "ResponseTemplate loaded (enterprise format)"),
]
for name, detail in steps:
    time.sleep(0.15)
    print(f"  {c('1;32','✓')} {c('1',name):20s} {c('2',detail)}")

time.sleep(0.3)
print(c("1;33", "\n  HistoryWindow: 3-turn sliding window (saves ~77% tokens)"))
print(c("1;33", "  ErrorSanitizer: ABAP/SAP errors → user-friendly messages"))
time.sleep(0.4)

section("2 · INCOMING QUERY")
time.sleep(0.2)
slow(f'  User: {c("1;37","Show me open maintenance orders for plant 1010")}', 0.025)
time.sleep(0.5)

section("3 · PLANNER → INTENT CLASSIFICATION")
time.sleep(0.3)
print(f"  Intent:      {c('1;33','maintenance_query')}  (confidence: 0.97)")
time.sleep(0.15)
print(f"  Tool group:  {c('1;33','sap_maintenance')}")
time.sleep(0.15)
print(f"  Tools bound: {c('36','get_orders, get_order_details')}")
time.sleep(0.15)
print(f"  Context:     {c('2','3 turns • 1,240 tokens (vs 18,400 naive)')}")
time.sleep(0.4)

section("4 · EXECUTOR → TOOL CALLS")
time.sleep(0.2)
print(f"  {c('33','▸')} Calling {c('1','get_orders')}(plant='1010', status='open') ...")
time.sleep(0.6)
print(f"    {c('32','←')} 3 orders returned in {c('1','0.8s')}")
time.sleep(0.15)

orders = [
    ("4001234", "Pump overhaul",     "PM01", "High",   "2026-05-01"),
    ("4001235", "Conveyor belt check","PM03", "Medium", "2026-05-03"),
    ("4001236", "HVAC filter replace","PM02", "Low",    "2026-05-07"),
]
print()
print(f"  {c('1','Order'):12s} {c('1','Description'):24s} {c('1','Type'):8s} {c('1','Priority'):10s} {c('1','Due')}")
print(f"  {'─'*12} {'─'*24} {'─'*8} {'─'*10} {'─'*10}")
for oid, desc, typ, prio, due in orders:
    pcolor = '31' if prio == 'High' else '33' if prio == 'Medium' else '2'
    print(f"  {oid:12s} {desc:24s} {typ:8s} {c(pcolor, prio):18s} {due}")
    time.sleep(0.1)
time.sleep(0.3)

section("5 · OBSERVER → QUALITY GATE")
time.sleep(0.2)
checks = [
    ("Data completeness", "✓ 3/3 orders have all fields"),
    ("Confidence score",  "✓ 0.97 ≥ 0.85 threshold"),
    ("Error check",       "✓ No ABAP errors detected"),
    ("Token budget",      "✓ 4,180 tokens (budget: 5,000)"),
]
for name, detail in checks:
    time.sleep(0.12)
    print(f"  {c('32','✓')} {name:22s} {c('2',detail)}")

print(f"\n  {c('1;32','▶ PASS')} — forwarding to Synthesiser")
time.sleep(0.4)

section("6 · SYNTHESISER → FORMATTED RESPONSE")
time.sleep(0.3)
slow(f"  {c('1;37','You have 3 open maintenance orders for plant 1010:')}", 0.02)
time.sleep(0.1)
slow(f"  {c('1;31','⚠ HIGH')}  {c('37','4001234 — Pump overhaul (due May 1)')}", 0.02)
slow(f"  {c('1;33','● MED')}   {c('37','4001235 — Conveyor belt check (due May 3)')}", 0.02)
slow(f"  {c('2','○ LOW')}   {c('37','4001236 — HVAC filter replace (due May 7)')}", 0.02)
time.sleep(0.2)
print(f"\n  {c('2','Quick replies:')} {c('36','[Show details]  [Create work order]  [Export CSV]')}")

time.sleep(0.5)
print(c("1;36", f"\n{'─'*60}"))
print(c("1;32", "  ✓ Done in 3.8s • 4,180 tokens • $0.003 cost"))
print(c("2",    "    (Naive agent: 12.3s • 18,400 tokens • $0.015)"))
print(c("1;36", f"{'─'*60}\n"))
time.sleep(1.0)
