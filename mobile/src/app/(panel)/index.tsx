import { useQuery } from "@tanstack/react-query";
import { StyleSheet, Text, View } from "react-native";

import { BalanceOrbit, groupByCurrency } from "@/components/balance-orbit";
import { AccountCard } from "@/components/currency";
import { BudgetsCard, RunwayCard } from "@/components/habits";
import { Button, ErrorState, LinkBanner, Loading, Screen, styles } from "@/components/ui";
import { formatMonth, formatUsd, localToday, RATE_SOURCE_LABELS } from "@/lib/format";
import { daysLeftInMonth, runway } from "@/lib/habits";
import { useLinkedUser } from "@/lib/hooks";
import {
  type Balance,
  type BudgetRow,
  getBalances,
  getBudgets,
  getPeriodTotals,
  getSpendingPace,
} from "@/lib/queries";
import { supabase } from "@/lib/supabase";
import { colors, radius } from "@/theme";

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
  const budgets = useQuery({ queryKey: ["budgets", today], queryFn: getBudgets, enabled: linked });
  const pace = useQuery({ queryKey: ["pace", today], queryFn: getSpendingPace, enabled: linked });

  const queries = [balances, month, budgets, pace];
  const refreshing = user.isRefetching || queries.some((q) => q.isRefetching);
  function refresh() {
    void user.refetch();
    if (linked) for (const q of queries) void q.refetch();
  }

  let body;
  if (user.isPending) body = <Loading />;
  else if (user.isError) body = <ErrorState onRetry={refresh} />;
  else if (!user.data) body = <LinkBanner />;
  else if (balances.isPending) body = <Loading />;
  else if (balances.isError) body = <ErrorState onRetry={refresh} />;
  else {
    body = (
      <Overview
        balances={balances.data}
        month={month.data}
        vesSource={user.data.vesRateSource}
        pace={pace.data}
        budgets={budgets.data}
        today={today}
      />
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
  pace,
  budgets,
  today,
}: {
  balances: Balance[];
  month: { incomeUsd: number; expensesUsd: number } | undefined;
  vesSource: string;
  pace: { windowDays: number | null; expensesUsd: number } | undefined;
  budgets: BudgetRow[] | undefined;
  today: string;
}) {
  // Igual que la web: suma de los equivalentes que ya calculó la vista account_balances_usd.
  const totalUsd = balances.reduce((sum, b) => sum + (b.balanceUsd ?? 0), 0);
  const unpriced = balances.filter((b) => b.balanceUsd === null && b.balance !== 0);
  const stale = [...new Set(balances.filter((b) => b.rateStale).map((b) => b.rateSource ?? ""))];
  const groups = groupByCurrency(balances, totalUsd);

  return (
    <>
      <BalanceOrbit groups={groups} totalUsd={totalUsd} />
      <Text style={[styles.faint, { textAlign: "center" }]}>
        Toca una moneda para ver su saldo y sus movimientos. Los Bs con tu fuente:{" "}
        {RATE_SOURCE_LABELS[vesSource] ?? vesSource}.
      </Text>
      {unpriced.length > 0 ? (
        <Text style={stat.alert}>
          Sin tasa todavía para {unpriced.map((b) => b.name).join(", ")}: no suma al total.
        </Text>
      ) : null}
      {stale.length > 0 ? (
        <Text style={stat.alert}>
          Tasa vieja (más de 6 horas): {stale.map((s) => RATE_SOURCE_LABELS[s] ?? s).join(", ")}.
        </Text>
      ) : null}
      {month ? (
        <View style={{ flexDirection: "row", gap: 10 }}>
          <MonthStat
            label={`Ingresos de ${formatMonth(today)}`}
            value={formatUsd(month.incomeUsd)}
            color={colors.lime}
          />
          <MonthStat
            label={`Gastos de ${formatMonth(today)}`}
            value={formatUsd(month.expensesUsd)}
            color={colors.danger}
          />
        </View>
      ) : null}

      {pace ? <RunwayCard result={runway(totalUsd, pace.expensesUsd, pace.windowDays)} /> : null}
      {budgets ? <BudgetsCard rows={budgets} daysLeft={daysLeftInMonth(today)} /> : null}

      <Text style={styles.subtitle} accessibilityRole="header">
        Tus cuentas
      </Text>
      <View style={{ gap: 10 }}>
        {balances.map((b) => (
          <AccountCard key={b.accountId} b={b} totalUsd={totalUsd} />
        ))}
      </View>
    </>
  );
}

function MonthStat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <View style={stat.box}>
      <Text style={styles.muted}>{label}</Text>
      <Text style={{ color, fontSize: 16, fontWeight: "800" }}>{value}</Text>
    </View>
  );
}

const stat = StyleSheet.create({
  box: {
    flex: 1,
    backgroundColor: colors.surface,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.row,
    padding: 14,
    gap: 2,
  },
  alert: { color: colors.warn, fontSize: 13, fontWeight: "700" },
});
