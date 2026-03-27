"""
Benchmark runner for AgentForge vs Naive ReAct Agent.

Usage:
    python run_benchmark.py --tools 20 --requests 100 --model gpt-4o
"""

import argparse
import asyncio
import json
import time
import statistics
from dataclasses import dataclass, field


@dataclass
class BenchmarkResult:
    """Result of a single benchmark request."""
    intent: str
    tokens_input: int
    tokens_output: int
    latency_ms: int
    tools_bound: int
    tools_available: int
    resolution_method: str  # "regex", "keyword", "llm"
    error_leaked: bool
    write_safety_ok: bool
    format_consistent: bool


@dataclass 
class BenchmarkReport:
    """Aggregated benchmark results."""
    results: list[BenchmarkResult] = field(default_factory=list)

    @property
    def avg_tokens(self) -> float:
        return statistics.mean(r.tokens_input + r.tokens_output for r in self.results)
    
    @property
    def avg_latency_ms(self) -> float:
        return statistics.mean(r.latency_ms for r in self.results)
    
    @property
    def p50_latency(self) -> float:
        latencies = sorted(r.latency_ms for r in self.results)
        return latencies[len(latencies) // 2]
    
    @property
    def p99_latency(self) -> float:
        latencies = sorted(r.latency_ms for r in self.results)
        return latencies[int(len(latencies) * 0.99)]
    
    @property
    def error_leak_rate(self) -> float:
        return sum(1 for r in self.results if r.error_leaked) / len(self.results) * 100
    
    @property
    def avg_token_savings(self) -> float:
        return statistics.mean(
            1 - (r.tools_bound / r.tools_available) for r in self.results
        ) * 100
    
    @property
    def regex_resolution_rate(self) -> float:
        return sum(1 for r in self.results if r.resolution_method == "regex") / len(self.results) * 100

    def print_report(self):
        print("\n" + "=" * 60)
        print("  AgentForge Benchmark Report")
        print("=" * 60)
        print(f"  Requests:          {len(self.results)}")
        print(f"  Avg tokens:        {self.avg_tokens:.0f}")
        print(f"  Avg latency:       {self.avg_latency_ms:.0f}ms")
        print(f"  p50 latency:       {self.p50_latency:.0f}ms")
        print(f"  p99 latency:       {self.p99_latency:.0f}ms")
        print(f"  Tool binding savings: {self.avg_token_savings:.1f}%")
        print(f"  Regex resolution:  {self.regex_resolution_rate:.1f}%")
        print(f"  Error leak rate:   {self.error_leak_rate:.1f}%")
        print("=" * 60)


# Sample queries for benchmarking
BENCHMARK_QUERIES = [
    ("Show me order 4002310", "order_summary"),
    ("What are the costs for 4002310?", "costs"),
    ("List operations for order 4002310", "operations"),
    ("Show confirmations", "confirmations"),
    ("Find overdue orders in plant 1000", "search"),
    ("Close order 4002310", "close_order"),
    ("What's the status of 4002310?", "order_summary"),
    ("Cost breakdown please", "costs"),
    ("Search for critical maintenance orders", "search"),
    ("Show me all pending orders", "search"),
    ("TECO order 4002310", "close_order"),
    ("Work steps for 4002310", "operations"),
    ("Time entries for this order", "confirmations"),
    ("How much has been spent?", "costs"),
    ("What can you do?", "unknown"),
]


def main():
    parser = argparse.ArgumentParser(description="AgentForge Benchmark")
    parser.add_argument("--tools", type=int, default=20, help="Number of tools")
    parser.add_argument("--requests", type=int, default=100, help="Number of requests")
    parser.add_argument("--model", type=str, default="gpt-4o", help="LLM model")
    args = parser.parse_args()

    print(f"Running benchmark: {args.requests} requests, {args.tools} tools, {args.model}")
    print("(This is a benchmark scaffold — wire up real AgentForge instance for actual results)")

    report = BenchmarkReport()
    report.print_report() if report.results else print("\nConfigure LLM API key to run actual benchmarks.")


if __name__ == "__main__":
    main()
