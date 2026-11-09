"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

/**
 * Gráficas de una sola serie: un solo color (validado para modo claro y oscuro en
 * globals.css: --chart-mark), sin leyenda porque el título dice qué se muestra. El texto
 * usa tonos neutros, nunca el color de la serie. Cada gráfica tiene su tabla en la página.
 */
const MARK = "var(--chart-mark)";
const GRID = "var(--chart-grid)";
const INK = "var(--chart-ink)";
const tick = { fill: INK, fontSize: 12 };

const usd = new Intl.NumberFormat("es-VE", {
  style: "currency",
  currency: "USD",
  currencyDisplay: "narrowSymbol",
  maximumFractionDigits: 2,
});
const compactUsd = new Intl.NumberFormat("es-VE", {
  style: "currency",
  currency: "USD",
  currencyDisplay: "narrowSymbol",
  notation: "compact",
  maximumFractionDigits: 1,
});
const bs = new Intl.NumberFormat("es-VE", { maximumFractionDigits: 2 });

function shortDay(day: string) {
  const [y, m, d] = day.split("-").map(Number);
  return new Intl.DateTimeFormat("es-VE", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(y, m - 1, d)));
}

const tooltipStyle = {
  contentStyle: {
    background: "var(--background)",
    border: `1px solid ${GRID}`,
    borderRadius: 8,
    fontSize: 13,
  },
  labelStyle: { color: "var(--foreground)" },
  itemStyle: { color: "var(--foreground)" },
  cursor: { fill: GRID, fillOpacity: 0.4 },
};

export function CategoryChart({ data }: { data: { category: string; totalUsd: number }[] }) {
  const height = Math.max(120, data.length * 36 + 24);
  return (
    <div aria-hidden="true" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 72, bottom: 4, left: 8 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="category"
            width={96}
            tick={tick}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip {...tooltipStyle} formatter={(value) => [usd.format(Number(value)), "Gasto"]} />
          <Bar dataKey="totalUsd" fill={MARK} barSize={20} radius={[0, 4, 4, 0]}>
            <LabelList
              dataKey="totalUsd"
              position="right"
              formatter={(value) => usd.format(Number(value))}
              style={{ fill: INK, fontSize: 12 }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function WeeklyChart({ data }: { data: { weekStart: string; expensesUsd: number }[] }) {
  return (
    <div aria-hidden="true" className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis
            dataKey="weekStart"
            tickFormatter={shortDay}
            tick={tick}
            tickLine={false}
            axisLine={{ stroke: GRID }}
            interval="preserveStartEnd"
            minTickGap={16}
          />
          <YAxis
            tickFormatter={(v) => compactUsd.format(Number(v))}
            tick={tick}
            tickLine={false}
            axisLine={false}
            width={56}
          />
          <Tooltip
            {...tooltipStyle}
            labelFormatter={(label) => `Semana del ${shortDay(String(label))}`}
            formatter={(value) => [usd.format(Number(value)), "Gasto"]}
          />
          <Bar dataKey="expensesUsd" fill={MARK} maxBarSize={24} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function BolivarChart({ data }: { data: { day: string; bsPerUsd: number }[] }) {
  return (
    <div aria-hidden="true" className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis
            dataKey="day"
            tickFormatter={shortDay}
            tick={tick}
            tickLine={false}
            axisLine={{ stroke: GRID }}
            interval="preserveStartEnd"
            minTickGap={24}
          />
          <YAxis
            domain={["auto", "auto"]}
            tickFormatter={(v) => bs.format(Number(v))}
            tick={tick}
            tickLine={false}
            axisLine={false}
            width={64}
          />
          <Tooltip
            {...tooltipStyle}
            cursor={{ stroke: GRID }}
            labelFormatter={(label) => shortDay(String(label))}
            formatter={(value) => [`${bs.format(Number(value))} Bs`, "1 USD"]}
          />
          <Line
            type="monotone"
            dataKey="bsPerUsd"
            stroke={MARK}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            dot={false}
            activeDot={{ r: 4, stroke: "var(--background)", strokeWidth: 2, fill: MARK }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
