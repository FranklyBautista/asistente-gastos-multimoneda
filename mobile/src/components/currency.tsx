import { Text, View, type ViewStyle } from "react-native";

import { styles } from "@/components/ui";
import { CURRENCY_LABELS, type Currency, formatAmount, formatUsd } from "@/lib/format";
import type { Balance } from "@/lib/queries";
import { colors, radius } from "@/theme";

/** Color de acento por moneda, igual que la web (web/src/components/currency.tsx). */
export const CURRENCY_ACCENT: Record<Currency, string> = {
  VES: "#ffcf4d",
  COP: "#7cc4ff",
  USD: "#8dfb86",
  USDT: "#4fd8b0",
};

// Arco de estrellas de Venezuela y estrellas del cantón de EE. UU., en una caja de 24×24.
const VE_STARS = [
  [7, 13.6],
  [8.6, 11.4],
  [10.7, 10.1],
  [13.3, 10.1],
  [15.4, 11.4],
  [17, 13.6],
];
const US_STARS = [
  [2.5, 2.5],
  [5.5, 2.5],
  [8.5, 2.5],
  [4, 5.5],
  [7, 5.5],
  [2.5, 8.5],
  [5.5, 8.5],
  [8.5, 8.5],
];

/**
 * Ícono redondo de la moneda: la bandera del país, o la ₮ de Tether para USDT. Hecho con
 * vistas (sin react-native-svg). Decorativo: siempre va junto al código de la moneda.
 */
export function CurrencyIcon({ currency, size = 36 }: { currency: Currency; size?: number }) {
  // El borde de 1 px ocupa espacio: las medidas van sobre el área de adentro.
  const inner = size - 2;
  const k = inner / 24;
  const dots = (points: number[][], r: number) =>
    points.map(([cx, cy]) => (
      <View
        key={`${cx}-${cy}`}
        style={{
          position: "absolute",
          left: (cx - r) * k,
          top: (cy - r) * k,
          width: 2 * r * k,
          height: 2 * r * k,
          borderRadius: r * k,
          backgroundColor: "#fff",
        }}
      />
    ));

  let flag;
  if (currency === "VES") {
    flag = (
      <>
        <View style={{ flex: 1, backgroundColor: "#ffcc00" }} />
        <View style={{ flex: 1, backgroundColor: "#00247d" }} />
        <View style={{ flex: 1, backgroundColor: "#cf142b" }} />
        {dots(VE_STARS, 0.75)}
      </>
    );
  } else if (currency === "COP") {
    flag = (
      <>
        <View style={{ flex: 2, backgroundColor: "#fcd116" }} />
        <View style={{ flex: 1, backgroundColor: "#003893" }} />
        <View style={{ flex: 1, backgroundColor: "#ce1126" }} />
      </>
    );
  } else if (currency === "USD") {
    flag = (
      <>
        {Array.from({ length: 13 }, (_, i) => (
          <View key={i} style={{ flex: 1, backgroundColor: i % 2 ? "#fff" : "#b22234" }} />
        ))}
        <View
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            width: 11 * k,
            height: (7 / 13) * inner,
            backgroundColor: "#3c3b6e",
          }}
        />
        {dots(US_STARS, 0.7)}
      </>
    );
  } else {
    flag = (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <Text style={{ color: "#fff", fontSize: size * 0.62, fontWeight: "800", lineHeight: size }}>
          ₮
        </Text>
      </View>
    );
  }

  return (
    <View
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      style={{
        width: size,
        height: size,
        borderRadius: size / 2,
        overflow: "hidden",
        borderWidth: 1,
        borderColor: "rgba(255, 255, 255, 0.15)",
        backgroundColor: currency === "USDT" ? "#26a17b" : undefined,
      }}
    >
      {flag}
    </View>
  );
}

/** Tarjeta de una cuenta: ícono y color de su moneda, saldo y su peso en el consolidado. */
export function AccountCard({ b, totalUsd }: { b: Balance; totalUsd: number }) {
  const accent = CURRENCY_ACCENT[b.currency];
  const share =
    totalUsd > 0 && b.balanceUsd !== null && b.balanceUsd > 0
      ? Math.min(100, (b.balanceUsd / totalUsd) * 100)
      : null;
  const usdNote =
    b.currency === "USD"
      ? "Moneda base"
      : b.balanceUsd === null
        ? "Sin tasa"
        : `≈ ${formatUsd(b.balanceUsd)}`;
  return (
    <View style={[card, { borderColor: `${accent}55` }]}>
      <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
        <CurrencyIcon currency={b.currency} />
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={[styles.body, { fontWeight: "700" }]} numberOfLines={1}>
            {b.name}
          </Text>
          <Text style={{ color: accent, fontSize: 12, fontWeight: "800" }}>
            {CURRENCY_LABELS[b.currency]}
          </Text>
        </View>
        <View style={{ alignItems: "flex-end" }}>
          <Text
            style={{
              color: b.balance < 0 ? colors.danger : colors.foreground,
              fontSize: 17,
              fontWeight: "800",
            }}
          >
            {formatAmount(b.balance, b.currency)}
          </Text>
          <Text style={styles.faint}>{usdNote}</Text>
        </View>
      </View>
      {share !== null ? (
        <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
          <View style={bar}>
            <View
              style={{
                width: `${Math.max(share, 2)}%`,
                height: "100%",
                borderRadius: 3,
                backgroundColor: accent,
              }}
            />
          </View>
          <Text style={[styles.faint, { fontWeight: "600" }]}>{Math.round(share)}% del total</Text>
        </View>
      ) : null}
    </View>
  );
}

const card: ViewStyle = {
  backgroundColor: colors.surface,
  borderWidth: 1,
  borderRadius: radius.row,
  padding: 14,
  gap: 12,
};
const bar: ViewStyle = {
  flex: 1,
  height: 6,
  borderRadius: 3,
  overflow: "hidden",
  backgroundColor: "rgba(255, 255, 255, 0.1)",
};
