import { StyleSheet, Text, View } from "react-native";

import { Card, styles } from "@/components/ui";
import { formatAmount, formatUsd } from "@/lib/format";
import { budgetState, type BudgetState, daysText, type Runway, usedPct } from "@/lib/habits";
import type { BudgetRow } from "@/lib/queries";
import { colors } from "@/theme";

/** El colchón en días, con los mismos textos que /colchon en el bot. */
export function RunwayCard({ result }: { result: Runway }) {
  if (!result.known) {
    const text = {
      no_history: "Cuando lleves dos semanas anotando, verás para cuántos días te alcanza.",
      short_history: `Llevas ${daysText(result.historyDays)} anotando. Con dos semanas de gastos verás para cuántos días te alcanza.`,
      no_expenses: `No anotaste gastos en ${daysText(result.historyDays)}, así que todavía no se puede calcular.`,
    }[result.reason];
    return (
      <Card style={{ gap: 6 }}>
        <Text style={styles.label}>Colchón</Text>
        <Text style={styles.body}>{text}</Text>
      </Card>
    );
  }

  const window =
    result.windowDays >= 90
      ? "tu promedio de los últimos 90 días"
      : `tu promedio desde que empezaste a anotar hace ${daysText(result.windowDays)}`;
  return (
    <Card style={{ gap: 6 }}>
      <Text style={styles.label}>Colchón</Text>
      <Text
        style={local.big}
        accessibilityLabel={`Cubres unos ${daysText(result.days)} de tus gastos`}
      >
        {result.days === 0 ? "Menos de 1 día" : `≈ ${daysText(result.days)}`}
      </Text>
      <Text style={styles.muted}>
        Gastas {formatUsd(result.dailySpendUsd)} al día, {window}.
        {result.nextStep !== null ? ` Siguiente escalón: ${daysText(result.nextStep)}.` : ""}
      </Text>
      <Text style={styles.faint}>Lo que te deben no cuenta hasta que te lo paguen.</Text>
    </Card>
  );
}

const BAR_COLORS: Record<BudgetState, string> = {
  ok: colors.lime,
  near: colors.warn,
  over: colors.danger,
};

/** Topes del mes en USD: barra de avance y lo que queda, sin regaños (como el bot). */
export function BudgetsCard({ rows, daysLeft }: { rows: BudgetRow[]; daysLeft: number }) {
  return (
    <Card style={{ gap: 14 }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Text style={styles.label}>Topes del mes</Text>
        <Text style={styles.faint}>Quedan {daysText(daysLeft)}</Text>
      </View>
      {rows.length === 0 ? (
        <Text style={styles.muted}>
          Todavía no tienes topes. Pídeselo al bot, por ejemplo: «no quiero gastar más de 100
          dólares al mes en comida».
        </Text>
      ) : (
        rows.map((b) => <BudgetLine key={b.id} row={b} />)
      )}
    </Card>
  );
}

function BudgetLine({ row }: { row: BudgetRow }) {
  const state = budgetState(row.spentUsd, row.limitUsd);
  const pct = usedPct(row.spentUsd, row.limitUsd);
  const detail =
    state === "over"
      ? `${formatUsd(row.spentUsd - row.limitUsd)} por encima del tope`
      : `te quedan ${formatUsd(row.limitUsd - row.spentUsd)}`;
  return (
    <View
      style={{ gap: 6 }}
      accessible
      accessibilityLabel={`${row.category}: llevas ${formatAmount(row.spentUsd, "USD")} de ${formatUsd(row.limitUsd)}, ${detail}`}
    >
      <View style={{ flexDirection: "row", justifyContent: "space-between", gap: 12 }}>
        <Text style={[styles.body, { flexShrink: 1 }]} numberOfLines={1}>
          {row.category}
        </Text>
        <Text style={[styles.body, { fontWeight: "700" }]}>
          {formatAmount(row.spentUsd, "USD")} / {formatUsd(row.limitUsd)}
        </Text>
      </View>
      <View style={local.track}>
        <View
          style={[
            local.fill,
            { width: `${Math.min(pct, 100)}%`, backgroundColor: BAR_COLORS[state] },
          ]}
        />
      </View>
      <Text style={[styles.faint, state === "over" ? { color: colors.danger } : null]}>
        {pct} % · {detail}
      </Text>
    </View>
  );
}

const local = StyleSheet.create({
  big: { color: colors.foreground, fontSize: 28, fontWeight: "800", letterSpacing: -0.5 },
  track: { height: 8, borderRadius: 999, backgroundColor: colors.chip, overflow: "hidden" },
  fill: { height: 8, borderRadius: 999 },
});
