import { Text, View } from "react-native";

import { styles } from "@/components/ui";
import { CURRENCY_LABELS, formatAmount, formatDateTime, formatUsd } from "@/lib/format";
import type { TransactionRow } from "@/lib/queries";
import { colors } from "@/theme";

/** Un movimiento: qué fue, categoría y cuenta, fecha local y monto con su equivalente. */
export function TransactionItem({ t, timeZone }: { t: TransactionRow; timeZone: string }) {
  const income = t.kind === "income";
  const title = t.description || t.categoryName || (income ? "Ingreso" : "Gasto");
  const money = `${formatAmount(t.amount, t.currency)} ${CURRENCY_LABELS[t.currency]}`;
  return (
    <View style={[styles.row, { flexDirection: "row", justifyContent: "space-between", gap: 12 }]}>
      <View style={{ flexShrink: 1, gap: 2 }}>
        <Text style={[styles.body, { fontWeight: "700" }]} numberOfLines={1}>
          {title}
          {t.edited ? (
            <Text style={{ color: colors.limeSoft, fontSize: 12 }}> · corregido</Text>
          ) : null}
        </Text>
        <Text style={styles.muted} numberOfLines={1}>
          {t.categoryName ?? "sin categoría"} · {t.accountName}
        </Text>
        <Text style={styles.faint}>{formatDateTime(t.occurredAt, timeZone)}</Text>
      </View>
      <View style={{ alignItems: "flex-end" }}>
        <Text
          style={[
            styles.body,
            { fontWeight: "800", color: income ? colors.lime : colors.foreground },
          ]}
          accessibilityLabel={`${income ? "Ingreso" : "Gasto"} de ${money}`}
        >
          {income ? "+" : "−"}
          {money}
        </Text>
        {t.currency !== "USD" ? <Text style={styles.faint}>≈ {formatUsd(t.amountUsd)}</Text> : null}
      </View>
    </View>
  );
}
