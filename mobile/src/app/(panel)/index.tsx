import { useQuery } from "@tanstack/react-query";
import { StyleSheet, Text, View } from "react-native";

import { Button, Card, ErrorState, LinkBanner, Loading, Screen, styles } from "@/components/ui";
import {
  CURRENCY_LABELS,
  formatAmount,
  formatUsd,
  localToday,
  RATE_SOURCE_LABELS,
} from "@/lib/format";
import { useLinkedUser } from "@/lib/hooks";
import { type Balance, getBalances, getPeriodTotals } from "@/lib/queries";
import { supabase } from "@/lib/supabase";
import { colors } from "@/theme";

/** Saldos por cuenta, consolidado en USD y el mes en curso, como el Inicio de la web. */
export default function HomeScreen() {
  const user = useLinkedUser();
  const linked = Boolean(user.data);
  const today = user.data ? localToday(user.data.timezone) : "";
  const balances = useQuery({ queryKey: ["balances"], queryFn: getBalances, enabled: linked });
  const month = useQuery({
    queryKey: ["month", today],
    queryFn: () => getPeriodTotals(`${today.slice(0, 8)}01`, today),
    enabled: linked,
  });

  const refreshing = user.isRefetching || balances.isRefetching || month.isRefetching;
  function refresh() {
    void user.refetch();
    if (linked) {
      void balances.refetch();
      void month.refetch();
    }
  }

  let body;
  if (user.isPending) body = <Loading />;
  else if (user.isError) body = <ErrorState onRetry={refresh} />;
  else if (!user.data) body = <LinkBanner />;
  else if (balances.isPending) body = <Loading />;
  else if (balances.isError) body = <ErrorState onRetry={refresh} />;
  else {
    body = (
      <Overview balances={balances.data} month={month.data} vesSource={user.data.vesRateSource} />
    );
  }

  return (
    <Screen
      title="Tus finanzas"
      subtitle={user.data?.displayName ? `Hola, ${user.data.displayName}` : undefined}
      refreshing={refreshing}
      onRefresh={refresh}
    >
      {body}
      <Button label="Cerrar sesión" variant="ghost" onPress={() => void supabase.auth.signOut()} />
    </Screen>
  );
}

function Overview({
  balances,
  month,
  vesSource,
}: {
  balances: Balance[];
  month: { incomeUsd: number; expensesUsd: number } | undefined;
  vesSource: string;
}) {
  // Igual que la web: suma de los equivalentes que ya calculó la vista account_balances_usd.
  const totalUsd = balances.reduce((sum, b) => sum + (b.balanceUsd ?? 0), 0);
  const unpriced = balances.filter((b) => b.balanceUsd === null && b.balance !== 0);
  const stale = [...new Set(balances.filter((b) => b.rateStale).map((b) => b.rateSource ?? ""))];

  return (
    <>
      <View style={hero.box}>
        <Text style={hero.label}>Consolidado en USD</Text>
        <Text style={hero.total} testID="total-usd">
          {formatUsd(totalUsd)}
        </Text>
        <Text style={hero.note}>
          {balances.length} {balances.length === 1 ? "cuenta" : "cuentas"} · los Bs con tu fuente:{" "}
          {RATE_SOURCE_LABELS[vesSource] ?? vesSource}
        </Text>
        {unpriced.length > 0 ? (
          <Text style={hero.alert}>
            Sin tasa todavía para {unpriced.map((b) => b.name).join(", ")}: no suma al total.
          </Text>
        ) : null}
        {stale.length > 0 ? (
          <Text style={hero.alert}>
            Tasa vieja (más de 6 horas): {stale.map((s) => RATE_SOURCE_LABELS[s] ?? s).join(", ")}.
          </Text>
        ) : null}
        {month ? (
          <View style={{ flexDirection: "row", gap: 10, marginTop: 8 }}>
            <MonthStat label="Ingresos del mes" value={formatUsd(month.incomeUsd)} />
            <MonthStat label="Gastos del mes" value={formatUsd(month.expensesUsd)} />
          </View>
        ) : null}
      </View>

      <Text style={styles.subtitle} accessibilityRole="header">
        Tus cuentas
      </Text>
      <View style={{ gap: 10 }}>
        {balances.map((b) => (
          <Card
            key={b.accountId}
            style={{ flexDirection: "row", justifyContent: "space-between", gap: 12 }}
          >
            <Text style={[styles.body, { flexShrink: 1 }]} numberOfLines={1}>
              {b.name}
            </Text>
            <View style={{ alignItems: "flex-end" }}>
              <Text style={[styles.body, { fontWeight: "700" }]}>
                {formatAmount(b.balance, b.currency)} {CURRENCY_LABELS[b.currency]}
              </Text>
              <Text style={styles.faint}>{usdNote(b)}</Text>
            </View>
          </Card>
        ))}
      </View>
    </>
  );
}

function usdNote(b: Balance): string {
  if (b.currency === "USD") return "Base";
  return b.balanceUsd === null ? "Sin tasa" : `≈ ${formatUsd(b.balanceUsd)}`;
}

function MonthStat({ label, value }: { label: string; value: string }) {
  return (
    <View style={hero.stat}>
      <Text style={[hero.label, { fontSize: 12 }]}>{label}</Text>
      <Text style={[hero.label, { fontSize: 15, fontWeight: "800" }]}>{value}</Text>
    </View>
  );
}

const hero = StyleSheet.create({
  box: { backgroundColor: colors.lime, borderRadius: 24, padding: 20, gap: 4 },
  label: { color: colors.onLime, fontSize: 13, fontWeight: "600" },
  total: { color: colors.onLime, fontSize: 38, fontWeight: "800", letterSpacing: -1 },
  note: { color: colors.onLime, fontSize: 12 },
  alert: { color: colors.onLime, fontSize: 13, fontWeight: "700", marginTop: 4 },
  stat: {
    flex: 1,
    backgroundColor: "rgba(7, 43, 14, 0.1)",
    borderRadius: 18,
    padding: 12,
    gap: 2,
  },
});
