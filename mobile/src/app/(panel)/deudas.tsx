import { useQuery } from "@tanstack/react-query";
import { Text, View } from "react-native";

import { Card, Empty, ErrorState, LinkBanner, Loading, Screen, styles } from "@/components/ui";
import { CURRENCY_LABELS, formatAmount, formatDateTime } from "@/lib/format";
import { useLinkedUser } from "@/lib/hooks";
import { type DebtRow, getDebts } from "@/lib/queries";
import { colors } from "@/theme";

/** Pendientes arriba y liquidadas tachadas al final, desde debt_balances. */
export default function DebtsScreen() {
  const user = useLinkedUser();
  const debts = useQuery({ queryKey: ["debts"], queryFn: getDebts, enabled: Boolean(user.data) });
  const refresh = () => void (user.data ? debts.refetch() : user.refetch());

  let body;
  if (user.isPending || (user.data && debts.isPending)) body = <Loading />;
  else if (user.isError || debts.isError) body = <ErrorState onRetry={refresh} />;
  else if (!user.data) body = <LinkBanner />;
  else if (!debts.data?.length) {
    body = <Empty>Sin deudas. Anota una en Telegram: «le debo 20 dólares a Miguel».</Empty>;
  } else {
    const pending = debts.data.filter((d) => d.status !== "settled");
    const settled = debts.data.filter((d) => d.status === "settled");
    body = (
      <>
        <View style={{ flexDirection: "row", gap: 10 }}>
          <Totals title="Debes" debts={pending.filter((d) => d.direction === "i_owe")} />
          <Totals title="Te deben" debts={pending.filter((d) => d.direction === "owed_to_me")} />
        </View>
        <View style={{ gap: 10 }}>
          {[...pending, ...settled].map((d) => (
            <DebtItem key={d.id} d={d} timeZone={user.data!.timezone} />
          ))}
        </View>
      </>
    );
  }

  return (
    <Screen title="Deudas" refreshing={debts.isRefetching} onRefresh={refresh}>
      {body}
    </Screen>
  );
}

/** Lo pendiente por moneda: cada deuda sigue en su moneda original, sin convertir. */
function Totals({ title, debts }: { title: string; debts: DebtRow[] }) {
  const byCurrency = new Map<DebtRow["currency"], number>();
  for (const d of debts)
    byCurrency.set(d.currency, (byCurrency.get(d.currency) ?? 0) + d.remaining);
  return (
    <Card style={{ flex: 1, gap: 4, padding: 14 }}>
      <Text style={styles.muted}>{title}</Text>
      {byCurrency.size === 0 ? (
        <Text style={styles.faint}>Nada pendiente.</Text>
      ) : (
        [...byCurrency].map(([c, amount]) => (
          <Text key={c} style={[styles.body, { fontSize: 18, fontWeight: "800" }]}>
            {formatAmount(amount, c)} <Text style={styles.muted}>{CURRENCY_LABELS[c]}</Text>
          </Text>
        ))
      )}
    </Card>
  );
}

function DebtItem({ d, timeZone }: { d: DebtRow; timeZone: string }) {
  const done = d.status === "settled";
  const money = `${formatAmount(d.amount, d.currency)} ${CURRENCY_LABELS[d.currency]}`;
  const who =
    d.direction === "i_owe"
      ? `Le debes ${money} a ${d.counterparty}`
      : `${d.counterparty} te debe ${money}`;
  return (
    <View style={styles.row} accessibilityLabel={done ? `${who}, liquidada` : who}>
      <Text
        style={[
          styles.body,
          { fontWeight: "700" },
          done && { color: colors.muted, textDecorationLine: "line-through" },
        ]}
      >
        {who}
      </Text>
      {d.description ? <Text style={styles.muted}>{d.description}</Text> : null}
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Text style={styles.faint}>{formatDateTime(d.incurredAt, timeZone)}</Text>
        <Text style={{ color: done ? colors.faint : colors.warn, fontSize: 12, fontWeight: "700" }}>
          {done
            ? "Liquidada"
            : d.status === "partial"
              ? `Quedan ${formatAmount(d.remaining, d.currency)}`
              : "Pendiente"}
        </Text>
      </View>
    </View>
  );
}
