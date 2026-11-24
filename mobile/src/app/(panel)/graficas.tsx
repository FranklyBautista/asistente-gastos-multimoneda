import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Text, View } from "react-native";

import { BolivarChart, CategoryBars, DataTable, WeeklyChart } from "@/components/charts";
import {
  Card,
  Chip,
  Empty,
  ErrorState,
  LinkBanner,
  Loading,
  Screen,
  styles,
} from "@/components/ui";
import {
  BOLIVAR_DAYS,
  bolivarChange,
  bolivarSeries,
  bolivarVerdict,
  CHART_PERIODS,
  WEEKS,
} from "@/lib/charts";
import {
  formatAmount,
  formatDay,
  formatPercent,
  formatRate,
  formatUsd,
  localToday,
  RATE_SOURCE_LABELS,
} from "@/lib/format";
import { useLinkedUser } from "@/lib/hooks";
import {
  getBalances,
  getBolivarRates,
  getSpendingByCategory,
  getSpendingByWeek,
} from "@/lib/queries";

/** Las tres gráficas de la web: gasto por categoría, por semana y poder del bolívar. */
export default function ChartsScreen() {
  const user = useLinkedUser();
  const linked = Boolean(user.data);
  const timeZone = user.data?.timezone ?? "America/Caracas";
  const [days, setDays] = useState<number>(30);
  const from = localToday(timeZone, -(days - 1));
  const to = localToday(timeZone);

  const categories = useQuery({
    queryKey: ["spending-by-category", from, to],
    queryFn: () => getSpendingByCategory(from, to),
    enabled: linked,
  });
  const weeks = useQuery({
    queryKey: ["spending-by-week", WEEKS],
    queryFn: () => getSpendingByWeek(WEEKS),
    enabled: linked,
  });
  const bolivar = useQuery({
    queryKey: ["bolivar-rates", BOLIVAR_DAYS],
    queryFn: () => getBolivarRates(BOLIVAR_DAYS),
    enabled: linked,
  });
  const balances = useQuery({ queryKey: ["balances"], queryFn: getBalances, enabled: linked });

  const queries = [categories, weeks, bolivar, balances];
  const refreshing = user.isRefetching || queries.some((q) => q.isRefetching);
  function refresh() {
    void user.refetch();
    if (linked) for (const q of queries) void q.refetch();
  }

  let body;
  if (user.isPending) body = <Loading />;
  else if (user.isError) body = <ErrorState onRetry={refresh} />;
  else if (!user.data) body = <LinkBanner />;
  else {
    body = (
      <>
        <Card style={{ gap: 14 }}>
          <Text style={styles.subtitle} accessibilityRole="header">
            Gasto por categoría
          </Text>
          <View style={{ flexDirection: "row", gap: 8 }} accessibilityLabel="Periodo">
            {CHART_PERIODS.map((p) => (
              <Chip key={p} label={`${p} días`} selected={days === p} onPress={() => setDays(p)} />
            ))}
          </View>
          {categories.isPending ? (
            <Loading />
          ) : categories.isError ? (
            <ErrorState onRetry={() => void categories.refetch()} />
          ) : categories.data.length === 0 ? (
            <Empty>No hay gastos en este periodo.</Empty>
          ) : (
            <>
              <Text style={styles.muted}>
                Últimos {days} días, en USD al momento de cada gasto · total{" "}
                <Text style={{ color: styles.body.color, fontWeight: "700" }}>
                  {formatUsd(categories.data.reduce((sum, c) => sum + c.totalUsd, 0))}
                </Text>
              </Text>
              <CategoryBars data={categories.data} />
              <DataTable
                headers={["Categoría", "Gasto (USD)"]}
                rows={categories.data.map((c) => [c.category, formatUsd(c.totalUsd)])}
              />
            </>
          )}
        </Card>

        <Card style={{ gap: 14 }}>
          <Text style={styles.subtitle} accessibilityRole="header">
            Gasto por semana
          </Text>
          <Text style={styles.muted}>Últimas {WEEKS} semanas (de lunes a domingo), en USD.</Text>
          {weeks.isPending ? (
            <Loading />
          ) : weeks.isError ? (
            <ErrorState onRetry={() => void weeks.refetch()} />
          ) : (
            <>
              <WeeklyChart data={weeks.data} />
              <DataTable
                headers={["Semana del", "Gasto (USD)"]}
                rows={weeks.data.map((w) => [
                  formatDay(w.weekStart, "medium"),
                  formatUsd(w.expensesUsd),
                ])}
              />
            </>
          )}
        </Card>

        <Card style={{ gap: 14 }}>
          <Text style={styles.subtitle} accessibilityRole="header">
            Poder adquisitivo del bolívar
          </Text>
          {bolivar.isPending ? (
            <Loading />
          ) : bolivar.isError ? (
            <ErrorState onRetry={() => void bolivar.refetch()} />
          ) : (
            <Bolivar
              rates={bolivar.data}
              vesBalance={(balances.data ?? [])
                .filter((b) => b.currency === "VES")
                .reduce((sum, b) => sum + b.balance, 0)}
            />
          )}
        </Card>
      </>
    );
  }

  return (
    <Screen title="Gráficas" refreshing={refreshing} onRefresh={refresh}>
      {body}
    </Screen>
  );
}

function Bolivar({
  rates,
  vesBalance,
}: {
  rates: { day: string; source: string; usdPerUnit: number }[];
  vesBalance: number;
}) {
  const first = rates.at(0);
  const last = rates.at(-1);
  if (!first || !last)
    return <Empty>Todavía no hay tasas del bolívar guardadas con tu fuente.</Empty>;
  const series = bolivarSeries(rates);
  const change = bolivarChange(first.usdPerUnit, last.usdPerUnit);
  return (
    <>
      <Text style={styles.muted}>
        Bs por cada USD con la tasa {RATE_SOURCE_LABELS[last.source] ?? last.source}, desde el{" "}
        {formatDay(first.day, "medium")}. Si la línea sube, cada bolívar compra menos dólares.
      </Text>
      <Text style={[styles.title, { fontSize: 28 }]}>{formatPercent(change)}</Text>
      <Text style={styles.body}>
        {bolivarVerdict(change)}
        {vesBalance > 0
          ? ` Tu saldo de ${formatAmount(vesBalance, "VES")} Bs valía ${formatUsd(
              vesBalance * first.usdPerUnit,
            )} y hoy vale ${formatUsd(vesBalance * last.usdPerUnit)}.`
          : ""}
      </Text>
      <BolivarChart data={series} />
      <DataTable
        headers={["Día", "Bs por 1 USD"]}
        rows={series.map((r) => [formatDay(r.day, "medium"), formatRate(r.bsPerUsd)])}
      />
    </>
  );
}
