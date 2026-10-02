"use client";

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";

export type Bank = "BBCA" | "BBRI" | "BMRI" | "BBNI";
export type Metric = "roe" | "growth";
export const bankColors: Record<Bank, string> = { BBCA: "#9edab5", BBRI: "#a3b8ef", BMRI: "#dac28a", BBNI: "#b7a3d9" };
export const illustrativeSeries = {
  roe: [
    { period: "2021", BBCA: 18.3, BBRI: 14.1, BMRI: 16.2, BBNI: 9.1 },
    { period: "2022", BBCA: 20.2, BBRI: 17.6, BMRI: 19.8, BBNI: 11.2 },
    { period: "2023", BBCA: 22.1, BBRI: 19.5, BMRI: 21.2, BBNI: 13.1 },
    { period: "2024", BBCA: 23.4, BBRI: 18.8, BMRI: 22.6, BBNI: 13.9 },
    { period: "2025", BBCA: 24.2, BBRI: 19.1, BMRI: 22.8, BBNI: 14.7 },
  ],
  growth: [
    { period: "Q2 '25", BBCA: 11.2, BBRI: 5.4, BMRI: 9.5, BBNI: 3.8 },
    { period: "Q3 '25", BBCA: 12.1, BBRI: 7.2, BMRI: 10.3, BBNI: 4.1 },
    { period: "Q4 '25", BBCA: 10.8, BBRI: 5.1, BMRI: 9.6, BBNI: 5.3 },
    { period: "Q1 '26", BBCA: 13.4, BBRI: 7.8, BMRI: 11.2, BBNI: 4.4 },
    { period: "Q2 '26", BBCA: 12.8, BBRI: 8.2, BMRI: 10.6, BBNI: 6.1 },
  ],
};
const chartConfig = Object.fromEntries(Object.entries(bankColors).map(([key, color]) => [key, { label: key, color }])) satisfies ChartConfig;

export function ChartLineDefault({ metric = "roe", banks = ["BBCA", "BBRI", "BMRI", "BBNI"], compact = false }: { metric?: Metric; banks?: Bank[]; compact?: boolean }) {
  return <ChartContainer className={compact ? "line-chart compact" : "line-chart"} config={chartConfig}>
    <LineChart accessibilityLayer data={illustrativeSeries[metric]} margin={{ top: 14, left: 0, right: 14, bottom: 2 }}>
      <CartesianGrid vertical={false} stroke="#2b3031" strokeDasharray="3 5" />
      <XAxis dataKey="period" axisLine={false} tickLine={false} tickMargin={13} tick={{ fill: "#8d9491", fontSize: 11 }} />
      <YAxis axisLine={false} tickLine={false} width={42} tickFormatter={v => `${v}%`} tick={{ fill: "#8d9491", fontSize: 11 }} domain={[0, metric === "roe" ? 30 : 16]} tickCount={5} />
      <ChartTooltip cursor={{ stroke: "#55625b", strokeDasharray: "3 3" }} content={<ChartTooltipContent formatter={(value, name) => <div className="chart-tooltip-row"><span>{String(name)}</span><strong>{Number(value).toLocaleString("id-ID")}%</strong></div>} />} />
      {banks.map(bank => <Line key={bank} dataKey={bank} type="monotone" stroke={`var(--color-${bank})`} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 3, stroke: "#181c1b" }} isAnimationActive={false} />)}
    </LineChart>
  </ChartContainer>;
}
export default ChartLineDefault;
