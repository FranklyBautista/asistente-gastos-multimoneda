import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Button, Chip, styles } from "@/components/ui";
import { type TxFilters, PERIODS, withKind } from "@/lib/filters";
import { KIND_LABELS, type Kind } from "@/lib/format";
import type { Category } from "@/lib/queries";
import { colors, radius } from "@/theme";

/**
 * Hoja inferior con los filtros de tipo, días y categoría. Cada toque se aplica al momento;
 * «Listo» solo la cierra. Es un Modal del núcleo de React Native: no necesita dev build.
 */
export function FilterSheet({
  visible,
  filters,
  categories,
  onChange,
  onClose,
}: {
  visible: boolean;
  filters: TxFilters;
  categories: Category[];
  onChange: (filters: TxFilters) => void;
  onClose: () => void;
}) {
  const insets = useSafeAreaInsets();
  const kindOf = (id: string) => categories.find((c) => c.id === id)?.kind;
  const shown = filters.kind ? categories.filter((c) => c.kind === filters.kind) : categories;

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable
        style={sheet.backdrop}
        onPress={onClose}
        accessibilityRole="button"
        accessibilityLabel="Cerrar filtros"
      />
      <View style={[sheet.panel, { paddingBottom: insets.bottom + 20 }]}>
        <View style={sheet.handle} />
        <Text style={styles.subtitle} accessibilityRole="header">
          Filtros
        </Text>

        <Section title="Tipo">
          <Chip
            label="Todos"
            selected={!filters.kind}
            onPress={() => onChange(withKind(filters, undefined, kindOf))}
          />
          {(Object.keys(KIND_LABELS) as Kind[]).map((k) => (
            <Chip
              key={k}
              label={KIND_LABELS[k]}
              selected={filters.kind === k}
              onPress={() => onChange(withKind(filters, k, kindOf))}
            />
          ))}
        </Section>

        <Section title="Fecha">
          <Chip
            label="Todo"
            selected={!filters.days}
            onPress={() => onChange({ ...filters, days: undefined })}
          />
          {PERIODS.map((d) => (
            <Chip
              key={d}
              label={`${d} días`}
              selected={filters.days === d}
              onPress={() => onChange({ ...filters, days: d })}
            />
          ))}
        </Section>

        <Text style={styles.label}>Categoría</Text>
        <ScrollView style={{ maxHeight: 220 }} contentContainerStyle={sheet.wrap}>
          <Chip
            label="Todas"
            selected={!filters.categoryId}
            onPress={() => onChange({ ...filters, categoryId: undefined })}
          />
          {shown.map((c) => (
            <Chip
              key={c.id}
              label={c.name}
              selected={filters.categoryId === c.id}
              onPress={() => onChange({ ...filters, categoryId: c.id })}
            />
          ))}
        </ScrollView>

        <View style={{ flexDirection: "row", gap: 10 }}>
          <View style={{ flex: 1 }}>
            <Button
              label="Limpiar"
              variant="ghost"
              onPress={() => onChange({ currency: filters.currency })}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Button label="Listo" onPress={onClose} />
          </View>
        </View>
      </View>
    </Modal>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ gap: 8 }}>
      <Text style={styles.label}>{title}</Text>
      <View style={sheet.wrap}>{children}</View>
    </View>
  );
}

const sheet = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: "rgba(0, 0, 0, 0.6)" },
  panel: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.card,
    borderTopRightRadius: radius.card,
    borderColor: colors.line,
    borderWidth: 1,
    paddingHorizontal: 20,
    paddingTop: 10,
    gap: 16,
  },
  handle: {
    alignSelf: "center",
    width: 40,
    height: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.line,
  },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
});
