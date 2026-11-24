import type { AssessResponse, BenchmarkResults, EvaluationReport, Health, Scenario } from "../types";

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url} -> ${res.status}`);
  return res.json();
}

export const fetchScenarios = () => getJson<Scenario[]>("/api/scenarios");
export const fetchEvaluation = () => getJson<EvaluationReport>("/api/evaluation");
export const fetchHealth = () => getJson<Health>("/api/health");

/** Held-out benchmark results; null when the backend has none yet. */
export async function fetchBenchmark(): Promise<BenchmarkResults | null> {
  const res = await fetch("/api/benchmark");
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Benchmark request failed");
  return res.json();
}

export async function assess(
  transcript: string,
  words: Array<{ text: string; confidence: number }>,
): Promise<AssessResponse> {
  const res = await fetch("/api/assess", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript, words }),
  });
  if (!res.ok) throw new Error("assess failed");
  return res.json();
}
