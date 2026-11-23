import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { FlatList, RefreshControl, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { FilterSheet } from "@/components/filter-sheet";
import { TransactionItem } from "@/components/transaction-item";
import { Chip, Empty, ErrorState, Header, LinkBanner, Loading, styles } from "@/components/ui";
import { sheetFilterCount, toQuery, type TxFilters } from "@/lib/filters";
import { CURRENCIES, CURRENCY_LABELS } from "@/lib/format";
import { useLinkedUser } from "@/lib/hooks";
import { getCategories, listTransactions, PAGE_SIZE } from "@/lib/queries";
import { colors } from "@/theme";

/** Lista paginada de list_transactions con los filtros de la web. Editar queda en la web. */
export default function TransactionsScreen() {
  const user = useLinkedUser();
  const [filters, setFilters] = useState<TxFilters>({});
  const [sheetOpen, setSheetOpen] = useState(false);
  const timeZone = user.data?.timezone ?? "America/Caracas";
  const params = toQuery(filters, timeZone);
  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: getCategories,
    enabled: Boolean(user.data),
    staleTime: Infinity,
  });
  const query = useInfiniteQuery({
    queryKey: ["transactions", params],
    queryFn: ({ pageParam }) => listTransactions(params, pageParam),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.page * PAGE_SIZE < last.total ? last.page + 1 : undefined),
    enabled: Boolean(user.data),
  });
  const rows = query.data?.pages.flatMap((p) => p.rows) ?? [];
  const active = sheetFilterCount(filters);

  let empty;
  if (user.isPending || (user.data && query.isPending)) empty = <Loading />;
  else if (user.isError || query.isError) {
    empty = <ErrorState onRetry={() => void (user.isError ? user.refetch() : query.refetch())} />;
  } else if (!user.data) empty = <LinkBanner />;
  else empty = <Empty>No hay movimientos con este filtro.</Empty>;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <FlatList
        data={rows}
        keyExtractor={(t) => t.id}
        contentContainerStyle={[styles.content, { gap: 10 }]}
        ListHeaderComponent={
          <View style={{ gap: 16, marginBottom: 6 }}>
            <Header title="Movimientos" />
            {user.data ? (
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={{ gap: 8 }}
              >
                <Chip
                  label={active ? `Filtros · ${active}` : "Filtros"}
                  selected={active > 0}
                  onPress={() => setSheetOpen(true)}
                />
                <Chip
                  label="Todas"
                  selected={!filters.currency}
                  onPress={() => setFilters({ ...filters, currency: undefined })}
                />
                {CURRENCIES.map((c) => (
                  <Chip
                    key={c}
                    label={CURRENCY_LABELS[c]}
                    selected={filters.currency === c}
                    onPress={() => setFilters({ ...filters, currency: c })}
                  />
                ))}
              </ScrollView>
            ) : null}
          </View>
        }
        renderItem={({ item }) => <TransactionItem t={item} timeZone={timeZone} />}
        ListEmptyComponent={empty}
        ListFooterComponent={query.isFetchingNextPage ? <Loading /> : undefined}
        onEndReached={() => {
          if (query.hasNextPage && !query.isFetchingNextPage) void query.fetchNextPage();
        }}
        onEndReachedThreshold={0.5}
        refreshControl={
          <RefreshControl
            refreshing={query.isRefetching && !query.isFetchingNextPage}
            onRefresh={() => void (user.data ? query.refetch() : user.refetch())}
            tintColor={colors.lime}
          />
        }
      />
      <FilterSheet
        visible={sheetOpen}
        filters={filters}
        categories={categories.data ?? []}
        onChange={setFilters}
        onClose={() => setSheetOpen(false)}
      />
    </SafeAreaView>
  );
}
