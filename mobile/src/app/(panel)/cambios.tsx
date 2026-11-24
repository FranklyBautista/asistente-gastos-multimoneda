import { useQuery } from "@tanstack/react-query";
import { Text, View } from "react-native";

import { Card, Empty, ErrorState, LinkBanner, Loading, Screen, styles } from "@/components/ui";
import {
  CURRENCY_LABELS,
  formatAmount,
  formatDateTime,
  formatPercent,
  formatRate,
} from "@/lib/format";
import { useLinkedUser } from "@/lib/hooks";
import { type ExchangeRow, getExchanges } from "@/lib/queries";
import { colors } from "@/theme";

/** Historial de exchange_history: tasa efectiva contra la de referencia y el promedio. */
export default function ExchangesScreen() {
  const user = useLinkedUser();
  const exchanges = useQuery({
    queryKey: ["exchanges"],
    queryFn: getExchanges,
    enabled: Boolean(user.data),
  });
  const refresh = () => void (user.data ? exchanges.refetch() : user.refetch());

  let body;
  if (user.isPending || (user.data && exchanges.isPending)) body = <Loading />;
  else if (user.isError || exchanges.isError) body = <ErrorState onRetry={refresh} />;
  else if (!user.data) body = <LinkBanner />;
  else if (!exchanges.data?.length) {
    body = (
      <Empty>Todavía no hay cambios. Anota uno en Telegram: «cambié 50 usdt a bs a 985».</Empty>
    );
  } else {
    const diffs = exchanges.data.flatMap((e) =>
      e.differencePct === null ? [] : [e.differencePct],
    );
    const average = diffs.length ? diffs.reduce((a, b) => a + b, 0) / diffs.length : null;
    body = (
      <>
        {average !== null ? (
          <Card style={{ gap: 4, borderColor: average >= 0 ? colors.lime : colors.line }}>
            <Text style={styles.muted}>Diferencia promedio contra la tasa de referencia</Text>
            <Text style={[styles.title, { color: average >= 0 ? colors.lime : colors.danger }]}>
              {formatPercent(average)}
            </Text>
          </Card>
        ) : null}
        <View style={{ gap: 10 }}>
          {exchanges.data.map((e) => (
            <ExchangeItem key={e.id} e={e} timeZone={user.data!.timezone} />
          ))}
        </View>
      </>
    );
  }

  return (
    <Screen title="Cambios" refreshing={exchanges.isRefetching} onRefresh={refresh}>
      {body}
    </Screen>
  );
}

function ExchangeItem({ e, timeZone }: { e: ExchangeRow; timeZone: string }) {
  const diff = e.differencePct;
  return (
    <View style={styles.row}>
      <Text style={[styles.body, { fontWeight: "700" }]}>
        {formatAmount(e.fromAmount, e.fromCurrency)} {CURRENCY_LABELS[e.fromCurrency]} →{" "}
        {formatAmount(e.toAmount, e.toCurrency)} {CURRENCY_LABELS[e.toCurrency]}
      </Text>
      <Text style={styles.muted}>
        Tasa {formatRate(e.effectiveRate)}
        {e.referenceRate !== null ? ` · referencia ${formatRate(e.referenceRate)}` : ""}
      </Text>
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Text style={styles.faint}>{formatDateTime(e.occurredAt, timeZone)}</Text>
        {diff !== null ? (
          <Text style={{ color: diff >= 0 ? colors.lime : colors.danger, fontWeight: "700" }}>
            {formatPercent(diff)}
          </Text>
        ) : null}
      </View>
    </View>
  );
}
