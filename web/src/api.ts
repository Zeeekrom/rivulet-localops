import type { Bootstrap, DemoRun } from "./types";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers }
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Keep the stable HTTP error when the response is not JSON.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export function fetchBootstrap(signal?: AbortSignal): Promise<Bootstrap> {
  return requestJson<Bootstrap>("/demo/v1/bootstrap", { signal });
}

export function runScenario(scenarioId: string): Promise<DemoRun> {
  return requestJson<DemoRun>(`/demo/v1/scenarios/${encodeURIComponent(scenarioId)}/run`, {
    method: "POST"
  });
}
