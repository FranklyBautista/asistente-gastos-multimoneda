import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ScrollView, Text, TextInput, View } from "react-native";

import { Button, Card, Chip, Empty, ErrorState, Loading, styles } from "@/components/ui";
import { categoryOptions, parseAmount, pickCategory } from "@/lib/edit";
import { DEBT_LINKED_MESSAGE, editErrorMessage } from "@/lib/edit-errors";
import { CURRENCY_LABELS, formatDateTime, type Kind, KIND_LABELS } from "@/lib/format";
import { useLinkedUser } from "@/lib/hooks";
import {
  type Account,
  type Category,
  type EditableTransaction,
  editTransaction,
  getAccounts,
  getCategories,
  getTransaction,
} from "@/lib/queries";
import { colors } from "@/theme";

/**
 * Edición de un movimiento con edit_transaction, como /movimientos/editar en la web: tipo,
 * monto, cuenta y categoría. Los pagos de deuda no se editan (debt_linked).
 */
export default function EditScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const user = useLinkedUser();
  const transaction = useQuery({
    queryKey: ["transaction", id],
    queryFn: () => getTransaction(id),
    enabled: Boolean(id),
    staleTime: 0,
  });
  const accounts = useQuery({ queryKey: ["accounts"], queryFn: getAccounts });
  const categories = useQuery({
    queryKey: ["categories"],
    queryFn: getCategories,
    staleTime: Infinity,
  });
  const all = [transaction, accounts, categories];

  let body;
  if (all.some((q) => q.isPending)) body = <Loading />;
  else if (all.some((q) => q.isError)) {
    body = <ErrorState onRetry={() => all.forEach((q) => void q.refetch())} />;
  } else if (!transaction.data) body = <Empty>Ese movimiento no existe o ya se deshizo.</Empty>;
  else if (transaction.data.debtLinked) {
    body = (
      <Card>
        <Text style={styles.body}>{DEBT_LINKED_MESSAGE}</Text>
      </Card>
    );
  } else {
    body = (
      <EditForm
        transaction={transaction.data}
        accounts={accounts.data ?? []}
        categories={categories.data ?? []}
        dateLabel={formatDateTime(
          transaction.data.occurredAt,
          user.data?.timezone ?? "America/Caracas",
        )}
      />
    );
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.background }}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      {body}
    </ScrollView>
  );
}

function EditForm({
  transaction,
  accounts,
  categories,
  dateLabel,
}: {
  transaction: EditableTransaction;
  accounts: Account[];
  categories: Category[];
  dateLabel: string;
}) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<Kind>(transaction.kind);
  const [amountText, setAmountText] = useState(String(transaction.amount).replace(".", ","));
  const [accountId, setAccountId] = useState(transaction.accountId);
  const [categoryId, setCategoryId] = useState<string | null>(transaction.categoryId);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const currency = accounts.find((a) => a.id === accountId)?.currency ?? transaction.currency;
  const options = categoryOptions(categories, kind, transaction.categoryId);
  const category = pickCategory(options, categoryId);

  async function save() {
    const amount = parseAmount(amountText);
    if (amount === null) return setError(editErrorMessage("invalid_amount"));
    if (!category) return setError(editErrorMessage("category_mismatch"));
    setBusy(true);
    setError(null);
    try {
      await editTransaction({ id: transaction.id, kind, amount, accountId, categoryId: category });
      // Cambian saldos, totales del mes, topes y colchón: se recarga todo.
      await queryClient.invalidateQueries();
      router.back();
    } catch (e) {
      setError(editErrorMessage(e instanceof Error ? e.message : undefined));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ gap: 18 }}>
      <View style={{ gap: 2 }}>
        {transaction.description ? (
          <Text style={styles.subtitle}>{transaction.description}</Text>
        ) : null}
        <Text style={styles.faint}>{dateLabel}</Text>
      </View>

      <Group title="Tipo">
        {(Object.keys(KIND_LABELS) as Kind[]).map((k) => (
          <Chip key={k} label={KIND_LABELS[k]} selected={kind === k} onPress={() => setKind(k)} />
        ))}
      </Group>

      <View style={{ gap: 6 }}>
        <Text style={styles.label}>Monto en {CURRENCY_LABELS[currency]}</Text>
        <TextInput
          accessibilityLabel={`Monto en ${CURRENCY_LABELS[currency]}`}
          value={amountText}
          onChangeText={setAmountText}
          keyboardType="decimal-pad"
          selectTextOnFocus
          style={[styles.input, { fontSize: 22, fontWeight: "800" }]}
          placeholderTextColor={colors.faint}
        />
      </View>

      <Group title="Cuenta">
        {accounts.map((a) => (
          <Chip
            key={a.id}
            label={a.name}
            selected={accountId === a.id}
            onPress={() => setAccountId(a.id)}
          />
        ))}
      </Group>

      <Group title="Categoría">
        {options.map((c) => (
          <Chip
            key={c.id}
            label={c.name}
            selected={category === c.id}
            onPress={() => setCategoryId(c.id)}
          />
        ))}
      </Group>

      {error ? (
        <Text style={styles.error} accessibilityLiveRegion="polite">
          {error}
        </Text>
      ) : null}
      <Button label={busy ? "Guardando…" : "Guardar cambios"} onPress={save} disabled={busy} />
      <Text style={[styles.faint, { textAlign: "center" }]}>
        Si cambias la moneda, el equivalente en USD se recalcula con la tasa de cuando lo anotaste.
        Cada cambio queda como corrección y el bot lo usa como ejemplo.
      </Text>
    </View>
  );
}

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ gap: 8 }}>
      <Text style={styles.label}>{title}</Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>{children}</View>
    </View>
  );
}
