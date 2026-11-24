import { router } from "expo-router";
import { Pressable, Text, useWindowDimensions, View } from "react-native";

import { CURRENCY_ACCENT, CurrencyIcon } from "@/components/currency";
import { CURRENCIES, CURRENCY_LABELS, type Currency, formatUsd } from "@/lib/format";
import type { Balance } from "@/lib/queries";
import { colors } from "@/theme";

/** Saldo de todas las cuentas de una moneda y su parte del consolidado (igual que la web). */
export type CurrencyGroup = {
  currency: Currency;
  balance: number;
  /** null si ninguna cuenta de la moneda tiene tasa todavía. */
  balanceUsd: number | null;
  /** Porcentaje del consolidado (0–100), o null si no suma. */
  share: number | null;
};

export function groupByCurrency(balances: Balance[], totalUsd: number): CurrencyGroup[] {
  return CURRENCIES.flatMap((currency) => {
    const accounts = balances.filter((b) => b.currency === currency);
    if (accounts.length === 0) return [];
    const priced = accounts.filter((b) => b.balanceUsd !== null);
    const balanceUsd = priced.length ? priced.reduce((s, b) => s + (b.balanceUsd ?? 0), 0) : null;
    return [
      {
        currency,
        balance: accounts.reduce((s, b) => s + b.balance, 0),
        balanceUsd,
        share:
          totalUsd > 0 && balanceUsd !== null && balanceUsd > 0
            ? Math.min(100, (balanceUsd / totalUsd) * 100)
            : null,
      },
    ];
  });
}

/** Ángulos (grados, 0 = derecha, sentido horario) de cada burbuja alrededor del centro. */
function angles(n: number): number[] {
  // Con 4 monedas: Bs arriba a la izquierda, COP arriba a la derecha, USD y USDT abajo.
  if (n === 4) return [-135, -45, 135, 45];
  return Array.from({ length: n }, (_, i) => -90 + (i * 360) / n);
}

function circle(d: number) {
  return { width: d, height: d, borderRadius: d / 2 };
}

/**
 * El consolidado en una burbuja central con cada moneda alrededor. Tocar una moneda abre su
 * detalle (saldo y movimientos).
 */
export function BalanceOrbit({ groups, totalUsd }: { groups: CurrencyGroup[]; totalUsd: number }) {
  const { width } = useWindowDimensions();
  const size = Math.min(width - 40, 380);
  const core = size * 0.58;
  const bubble = size * 0.27;
  const orbit = size * 0.39; // radio
  const positions = angles(groups.length);

  return (
    <View style={{ width: size, height: size, alignSelf: "center" }}>
      {/* Órbita punteada. */}
      <View
        style={[
          circle(orbit * 2),
          {
            position: "absolute",
            left: size / 2 - orbit,
            top: size / 2 - orbit,
            borderWidth: 1,
            borderStyle: "dashed",
            borderColor: "rgba(255, 255, 255, 0.15)",
          },
        ]}
      />

      {/* Centro: el consolidado. */}
      <View
        style={[
          circle(core),
          {
            position: "absolute",
            left: (size - core) / 2,
            top: (size - core) / 2,
            alignItems: "center",
            justifyContent: "center",
            paddingHorizontal: core * 0.08,
            backgroundColor: "#0c1a0f",
            borderWidth: 2,
            borderColor: colors.lime,
            shadowColor: colors.lime,
            shadowOpacity: 0.6,
            shadowRadius: 24,
            shadowOffset: { width: 0, height: 0 },
            elevation: 12,
          },
        ]}
      >
        <Text style={{ color: colors.muted, fontSize: 13, fontWeight: "600" }}>Saldo total</Text>
        <Text
          style={{ color: colors.foreground, fontSize: size * 0.085, fontWeight: "800" }}
          numberOfLines={1}
          adjustsFontSizeToFit
          testID="total-usd"
        >
          {formatUsd(totalUsd)}
        </Text>
        <Text style={{ color: colors.faint, fontSize: 12, marginTop: 2 }}>consolidado en USD</Text>
      </View>

      {/* Una burbuja por moneda. */}
      {groups.map((g, i) => {
        const rad = (positions[i] * Math.PI) / 180;
        const label = g.currency === "VES" ? "VES / Bs" : CURRENCY_LABELS[g.currency];
        const color = CURRENCY_ACCENT[g.currency];
        return (
          <Pressable
            key={g.currency}
            onPress={() =>
              router.push({ pathname: "/moneda/[codigo]", params: { codigo: g.currency } })
            }
            accessibilityRole="button"
            accessibilityLabel={label}
            accessibilityHint="Abre su saldo y sus movimientos"
            style={({ pressed }) => [
              circle(bubble),
              {
                position: "absolute",
                left: size / 2 + orbit * Math.cos(rad) - bubble / 2,
                top: size / 2 + orbit * Math.sin(rad) - bubble / 2,
                alignItems: "center",
                justifyContent: "center",
                gap: 3,
                backgroundColor: "#13251a",
                borderWidth: 1.5,
                borderColor: pressed ? color : `${color}88`,
                shadowColor: color,
                shadowOpacity: 0.35,
                shadowRadius: 10,
                shadowOffset: { width: 0, height: 0 },
                elevation: 8,
                transform: [{ scale: pressed ? 0.95 : 1 }],
              },
            ]}
          >
            <CurrencyIcon currency={g.currency} size={bubble * 0.38} />
            <Text style={{ color: colors.foreground, fontSize: 12, fontWeight: "800" }}>
              {label}
            </Text>
            {g.share !== null ? (
              <Text style={{ color: colors.muted, fontSize: 10, fontWeight: "600" }}>
                {Math.round(g.share)}%
              </Text>
            ) : null}
          </Pressable>
        );
      })}
    </View>
  );
}
