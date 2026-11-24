import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Redirect, useLocalSearchParams } from "expo-router";
import { FlatList, RefreshControl, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { BackButton, CurrencyHero } from "@/components/currency-hero";
import { MovementRow } from "@/components/transaction-item";
import { Empty, ErrorState, LinkBanner, Loading, styles } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { CURRENCY_LABELS, isCurrency } from "@/lib/format";
import { useLinkedUser } from "@/lib/hooks";
import { getBalances, listTransactions, PAGE_SIZE } from "@/lib/queries";
import { colors, radius } from "@/theme";

/** Detalle de una moneda (se abre desde la burbuja del Inicio): su saldo y sus movimientos. */
export default function CurrencyScreen() {
  const { session, loading } = useAuth();
  const { codigo } = useLocalSearchParams<{ codigo: string }>();
  const code = String(codigo ?? "").toUpperCase();
  const currency = isCurrency(code) ? code : undefined;

  const user = useLinkedUser();
  const linked = Boolean(user.data);
  const balances = useQuery({ queryKey: ["balances"], queryFn: getBalances, enabled: linked });
  // Llave propia: la pestaña Movimientos usa ["transactions", filtros].
  const movements = useInfiniteQuery({
    queryKey: ["transactions", currency],
    queryFn: ({ pageParam }) => listTransactions({ currency }, pageParam),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.page * PAGE_SIZE < last.total ? last.page + 1 : undefined),
    enabled: linked && Boolean(currency),
  });

  if (loading) return <Loading />;
  if (!session) return <Redirect href="/login" />;

  const rows = movements.data?.pages.flatMap((p) => p.rows) ?? [];
  const timeZone = user.data?.timezone ?? "America/Caracas";

  let empty;
  if (!currency) empty = <Empty>Esa moneda no existe.</Empty>;
  else if (user.isPending || (linked && movements.isPending)) empty = <Loading />;
  else if (user.isError || movements.isError) {
    empty = (
      <ErrorState onRetry={() => void (user.isError ? user.refetch() : movements.refetch())} />
    );
  } else if (!user.data) empty = <LinkBanner />;
  else empty = <Empty>{`Todavía no hay movimientos en ${CURRENCY_LABELS[currency]}.`}</Empty>;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <FlatList
        data={rows}
        keyExtractor={(t) => t.id}
        contentContainerStyle={styles.content}
        ListHeaderComponent={
          <View style={{ gap: 20, marginBottom: 12 }}>
            {currency && balances.data ? (
              <CurrencyHero currency={currency} balances={balances.data} />
            ) : (
              <BackButton />
            )}
            {currency && linked ? (
              <Text style={[styles.title, { fontSize: 22 }]} accessibilityRole="header">
                Movimientos
              </Text>
            ) : null}
          </View>
        }
        renderItem={({ item, index }) => (
          <View
            style={{
              backgroundColor: colors.surface,
              borderColor: colors.line,
              borderLeftWidth: 1,
              borderRightWidth: 1,
              borderTopWidth: index === 0 ? 1 : 0,
              borderBottomWidth: index === rows.length - 1 ? 1 : 0,
              borderTopLeftRadius: index === 0 ? radius.card : 0,
              borderTopRightRadius: index === 0 ? radius.card : 0,
              borderBottomLeftRadius: index === rows.length - 1 ? radius.card : 0,
              borderBottomRightRadius: index === rows.length - 1 ? radius.card : 0,
              paddingHorizontal: 16,
            }}
          >
            {index > 0 ? <View style={{ height: 1, backgroundColor: colors.line }} /> : null}
            <MovementRow t={item} timeZone={timeZone} />
          </View>
        )}
        ListEmptyComponent={empty}
        ListFooterComponent={movements.isFetchingNextPage ? <Loading /> : undefined}
        onEndReached={() => {
          if (movements.hasNextPage && !movements.isFetchingNextPage) {
            void movements.fetchNextPage();
          }
        }}
        onEndReachedThreshold={0.5}
        refreshControl={
          <RefreshControl
            refreshing={
              (movements.isRefetching && !movements.isFetchingNextPage) || balances.isRefetching
            }
            onRefresh={() => {
              void user.refetch();
              if (linked) {
                void balances.refetch();
                void movements.refetch();
              }
            }}
            tintColor={colors.lime}
          />
        }
      />
    </SafeAreaView>
  );
}
