import { backendFetch, backendUrl } from "@/lib/backend";
import type { AgentStatus, MetricDirection } from "@/lib/agent";

export const dynamic = "force-dynamic";

/** Reports whether the agent backend is configured and reachable (no Sectors credits used). */
export async function GET(): Promise<Response> {
  if (!backendUrl()) return Response.json({ live: false } satisfies AgentStatus);
  try {
    const response = await backendFetch("/v1/capabilities", { method: "GET" }, 5_000);
    if (!response.ok) return Response.json({ live: false } satisfies AgentStatus);
    const caps = (await response.json()) as {
      data_mode: string;
      llm_provider: string;
      metrics: Record<string, { id: string; en: string; direction?: MetricDirection }>;
    };
    const metrics = Object.fromEntries(Object.entries(caps.metrics).map(([key, label]) => [key, label.id]));
    const directions = Object.fromEntries(Object.entries(caps.metrics).map(([key, label]) => [key, label.direction ?? null]));
    return Response.json({
      live: true, dataSource: caps.data_mode, llmProvider: caps.llm_provider, metrics, directions,
    } satisfies AgentStatus);
  } catch {
    return Response.json({ live: false } satisfies AgentStatus);
  }
}
