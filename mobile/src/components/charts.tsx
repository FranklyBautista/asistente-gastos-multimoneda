import { matchFont } from "@shopify/react-native-skia";
import { useState } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { Bar, CartesianChart, Line } from "victory-native";

import { styles } from "@/components/ui";
import { compactUsd, shortDay } from "@/lib/charts";
import { formatRate, formatUsd } from "@/lib/format";
import { colors } from "@/theme";

/**
 * Gráficas de una sola serie, como la web (web/src/components/charts.tsx): un solo color
 * (--chart-mark), sin leyenda porque el título dice qué se muestra y texto en tonos neutros.
 * El lienzo de Skia va oculto a los lectores de pantalla: la tabla «Ver datos» es la
 * alternativa accesible.
 */
const MARK = colors.lime;
const GRID = colors.line;
const INK = colors.muted;

// Fuente del sistema para los ejes: no hace falta empaquetar un .ttf.
const font = matchFont({
  fontFamily: Platform.select({ ios: "Helvetica", default: "sans-serif" }),
  fontSize: 11,
});

const hidden = {
  accessibilityElementsHidden: true,
  importantForAccessibility: "no-hide-descendants",
} as const;

/** Barras horizontales con View: la categoría a la izquierda y el monto a la derecha. */
export function CategoryBars({ data }: { data: { category: string; totalUsd: number }[] }) {
  const max = Math.max(...data.map((d) => d.totalUsd), 0);
  return (
    <View style={{ gap: 10 }} {...hidden}>
      {data.map((d) => (
        <View key={d.category} style={{ gap: 4 }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", gap: 12 }}>
            <Text style={[styles.muted, { flexShrink: 1 }]} numberOfLines={1}>
              {d.category}
            </Text>
            <Text style={[styles.muted, { color: colors.foreground, fontWeight: "700" }]}>
              {formatUsd(d.totalUsd)}
            </Text>
          </View>
          <View style={local.track}>
            <View style={[local.fill, { width: `${max > 0 ? (d.totalUsd / max) * 100 : 0}%` }]} />
          </View>
        </View>
      ))}
    </View>
  );
}

export function WeeklyChart({ data }: { data: { weekStart: string; expensesUsd: number }[] }) {
  const points = data.map((w, i) => ({ i, usd: w.expensesUsd }));
  return (
    <View style={{ height: 220 }} {...hidden}>
      <CartesianChart
        data={points}
        xKey="i"
        yKeys={["usd"]}
        domainPadding={{ left: 14, right: 14, top: 12 }}
        domain={{ y: [0] }}
        xAxis={{
          font,
          labelColor: INK,
          lineColor: GRID,
          tickCount: 4,
          formatXLabel: (i) => (data[Number(i)] ? shortDay(data[Number(i)].weekStart) : ""),
        }}
        yAxis={[{ font, labelColor: INK, lineColor: GRID, tickCount: 4, formatYLabel: compactUsd }]}
        frame={{ lineWidth: 0 }}
      >
        {({ points: p, chartBounds }) => (
          <Bar
            points={p.usd}
            chartBounds={chartBounds}
            color={MARK}
            innerPadding={0.35}
            roundedCorners={{ topLeft: 6, topRight: 6 }}
          />
        )}
      </CartesianChart>
    </View>
  );
}

export function BolivarChart({ data }: { data: { day: string; bsPerUsd: number }[] }) {
  const points = data.map((d, i) => ({ i, bs: d.bsPerUsd }));
  return (
    <View style={{ height: 220 }} {...hidden}>
      <CartesianChart
        data={points}
        xKey="i"
        yKeys={["bs"]}
        domainPadding={{ top: 12, bottom: 12, right: 8 }}
        xAxis={{
          font,
          labelColor: INK,
          lineColor: GRID,
          tickCount: 3,
          formatXLabel: (i) => (data[Number(i)] ? shortDay(data[Number(i)].day) : ""),
        }}
        yAxis={[
          {
            font,
            labelColor: INK,
            lineColor: GRID,
            tickCount: 4,
            formatYLabel: (v) => formatRate(Number(v), 0),
          },
        ]}
        frame={{ lineWidth: 0 }}
      >
        {({ points: p }) => (
          <Line
            points={p.bs}
            color={MARK}
            strokeWidth={2.5}
            strokeCap="round"
            strokeJoin="round"
            curveType="monotoneX"
          />
        )}
      </CartesianChart>
    </View>
  );
}

/** La alternativa textual de cada gráfica: una tabla que se abre con «Ver datos». */
export function DataTable({
  headers,
  rows,
}: {
  headers: [string, string];
  rows: [string, string][];
}) {
  const [open, setOpen] = useState(false);
  return (
    <View style={{ gap: 6 }}>
      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen(!open)}
        hitSlop={8}
      >
        <Text style={[styles.label, { color: colors.lime }]}>
          {open ? "Ocultar datos" : "Ver datos"}
        </Text>
      </Pressable>
      {open ? (
        <View>
          <View style={local.row}>
            <Text style={styles.faint}>{headers[0]}</Text>
            <Text style={styles.faint}>{headers[1]}</Text>
          </View>
          {rows.map(([a, b]) => (
            <View key={a} style={[local.row, local.divider]} accessible>
              <Text style={styles.muted}>{a}</Text>
              <Text style={[styles.muted, { color: colors.foreground, fontWeight: "700" }]}>
                {b}
              </Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

const local = StyleSheet.create({
  track: { height: 10, borderRadius: 999, backgroundColor: colors.chip, overflow: "hidden" },
  fill: { height: 10, borderRadius: 999, backgroundColor: MARK },
  row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: 6 },
  divider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: GRID },
});
