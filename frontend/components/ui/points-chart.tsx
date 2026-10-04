"use client";

import * as React from "react";
import { Star } from "lucide-react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { cn } from "@/lib/utils";
import type { Lang } from "@/lib/i18n";

export interface PointsChartDataPoint {
  date: string;
  total: number;
  change: number | null;
}

export interface PointsChartLevel {
  value: number;
  color: string;
  label: string;
}

export interface PointsChartProps extends React.HTMLAttributes<HTMLDivElement> {
  data: PointsChartDataPoint[];
  height?: number;
  title?: string;
  headerRight?: React.ReactNode;
  yAxisLabel?: string;
  levels?: PointsChartLevel[];
  lineColor?: string;
  lang?: Lang;
}

function LevelReferenceStarLabel({ viewBox, color }: { viewBox?: { x?: number; y?: number } | null; color: string }) {
  const x = viewBox?.x;
  const y = viewBox?.y;
  if (typeof x !== "number" || typeof y !== "number") return null;
  return <g transform={`translate(${x - 13},${y})`}><Star x={-5} y={-5} width={10} height={10} fill={color} stroke={color} strokeWidth={1.75} /></g>;
}

export function PointsChart({
  data, height = 270, title, headerRight, yAxisLabel = "%", levels = [],
  lineColor = "var(--primary)", lang = "id", className, ...props
}: PointsChartProps) {
  const locale = lang === "id" ? "id-ID" : "en-US";
  const formatValue = (value: number) => value.toLocaleString(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  const yDomain = React.useMemo<[number, number]>(() => {
    const values = [...data.map(item => item.total), ...levels.map(level => level.value)].filter(Number.isFinite);
    if (!values.length) return [0, 100];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min;
    const padding = Math.max(range * 0.15, max * 0.08, 0.5);
    return [Math.min(0, min - padding), max + padding];
  }, [data, levels]);

  return <div className={cn("points-chart-card", className)} {...props}>
    {(title || headerRight) && <div className="points-chart-heading">{title && <strong>{title}</strong>}{headerRight && <span>{headerRight}</span>}</div>}
    <div className="points-chart-canvas" style={{ height }} role="img" aria-label={title}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 16, right: 22, left: 0, bottom: 4 }}>
          <CartesianGrid stroke="#3b4a40" strokeDasharray="3 5" vertical={false} />
          <XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fill: "#9daf9f", fontSize: 11 }} dy={8} />
          <YAxis tickLine={false} axisLine={false} domain={yDomain} tick={{ fill: "#9daf9f", fontSize: 10 }}
            tickFormatter={value => `${formatValue(Number(value))}%`} width={58}
            label={{ value: yAxisLabel, angle: -90, position: "insideLeft", fill: "#9daf9f", fontSize: 11, dx: -10 }} />
          {levels.map(level => <ReferenceLine key={`${level.label}-${level.value}`} y={level.value} stroke={level.color}
            strokeDasharray="6 6" strokeWidth={1.5} ifOverflow="extendDomain"
            label={{ position: "left", content: labelProps => <LevelReferenceStarLabel
              viewBox={labelProps.viewBox as { x?: number; y?: number } | null} color={level.color} /> }} />)}
          <Tooltip cursor={{ stroke: lineColor, strokeDasharray: "4 4" }} content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null;
            const row = payload[0].payload as PointsChartDataPoint;
            return <div className="points-chart-tooltip">
              <small>{label}</small>
              <strong>{formatValue(row.total)}%</strong>
              <span>{row.change === null ? (lang === "id" ? "Periode awal" : "First period")
                : `${row.change > 0 ? "+" : ""}${formatValue(row.change)} ${lang === "id" ? "poin persentase" : "pp"}`}</span>
            </div>;
          }} />
          <Line type="monotone" dataKey="total" stroke={lineColor} strokeWidth={3} connectNulls={false}
            dot={{ r: 4, fill: lineColor, stroke: "#15231a", strokeWidth: 2 }}
            activeDot={{ r: 7, fill: lineColor, stroke: "#e2f3e6", strokeWidth: 2 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
    <div className="points-chart-scale" aria-hidden="true">
      {data.map(point => <span key={point.date}><small>{point.date}</small><strong>{formatValue(point.total)}%</strong></span>)}
    </div>
    {levels.length > 0 && <div className="points-chart-levels">{levels.map(level => <span key={`${level.label}-${level.value}`}><Star size={11} fill={level.color} stroke={level.color} />{level.label}: {formatValue(level.value)}%</span>)}</div>}
  </div>;
}
