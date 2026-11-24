import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import { Pressable, Text, View } from "react-native";

import { CURRENCY_ACCENT, CurrencyIcon } from "@/components/currency";
import { styles } from "@/components/ui";
import { CURRENCY_LABELS, type Currency, formatAmount, formatUsd } from "@/lib/format";
import type { Balance } from "@/lib/queries";
import { colors, radius } from "@/theme";

const CURRENCY_NAMES: Record<Currency, string> = {
  VES: "Bolívar venezolano",
  COP: "Peso colombiano",
  USD: "Dólar estadounidense",
  USDT: "Tether",
};

function goBack() {
  if (router.canGoBack()) router.back();
  else router.replace("/");
}

export function BackButton() {
  return (
    <Pressable
      onPress={goBack}
      accessibilityRole="button"
      accessibilityLabel="Volver"
      hitSlop={8}
      style={{
        width: 44,
        height: 44,
        borderRadius: 22,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "rgba(255, 255, 255, 0.08)",
        borderWidth: 1,
        borderColor: colors.line,
      }}
    >
      <Ionicons name="chevron-back" size={22} color={colors.foreground} />
    </Pressable>
  );
}

/** Encabezado con el color de la moneda: ícono, saldo de todas sus cuentas y su equivalente. */
export function CurrencyHero({ currency, balances }: { currency: Currency; balances: Balance[] }) {
  const accent = CURRENCY_ACCENT[currency];
  const label = CURRENCY_LABELS[currency];
  const accounts = balances.filter((b) => b.currency === currency);
  const totalUsd = balances.reduce((s, b) => s + (b.balanceUsd ?? 0), 0);
  const balance = accounts.reduce((s, b) => s + b.balance, 0);
  const priced = accounts.filter((b) => b.balanceUsd !== null);
  const balanceUsd = priced.length ? priced.reduce((s, b) => s + (b.balanceUsd ?? 0), 0) : null;
  const share =
    totalUsd > 0 && balanceUsd !== null && balanceUsd > 0 ? (balanceUsd / totalUsd) * 100 : null;

  let note =
    currency === "USD"
      ? "Moneda base"
      : balanceUsd !== null
        ? `≈ ${formatUsd(balanceUsd)} USD`
        : "Sin tasa todavía: no suma al total";
  if (share !== null) note += ` · ${Math.round(share)}% de tu saldo total`;

  return (
    <View
      style={{
        backgroundColor: `${accent}1c`,
        borderColor: `${accent}55`,
        borderWidth: 1,
        borderRadius: radius.card,
        padding: 16,
        paddingBottom: 22,
        alignItems: "center",
        gap: 4,
      }}
    >
      <View style={{ alignSelf: "stretch" }}>
        <BackButton />
      </View>
      <View style={{ marginTop: -36 }}>
        <CurrencyIcon currency={currency} size={64} />
      </View>
      <Text
        style={{ color: colors.foreground, fontSize: 16, fontWeight: "800", marginTop: 6 }}
        accessibilityRole="header"
      >
        {currency === "VES" ? "VES / Bs" : label}
      </Text>
      <Text style={styles.faint}>{CURRENCY_NAMES[currency]}</Text>
      <Text
        style={{ color: colors.foreground, fontSize: 36, fontWeight: "800", marginTop: 10 }}
        numberOfLines={1}
        adjustsFontSizeToFit
        testID="currency-balance"
      >
        {formatAmount(balance, currency)}{" "}
        <Text style={{ color: accent, fontSize: 22 }}>{label}</Text>
      </Text>
      <Text style={[styles.muted, { textAlign: "center" }]}>{note}</Text>
      {accounts.length > 0 ? (
        <View
          style={{
            flexDirection: "row",
            flexWrap: "wrap",
            justifyContent: "center",
            gap: 8,
            marginTop: 14,
          }}
        >
          {accounts.map((a) => (
            <View
              key={a.accountId}
              style={{
                borderRadius: radius.pill,
                borderWidth: 1,
                borderColor: "rgba(255, 255, 255, 0.1)",
                backgroundColor: "rgba(255, 255, 255, 0.06)",
                paddingHorizontal: 14,
                paddingVertical: 8,
              }}
            >
              <Text style={{ color: colors.muted, fontSize: 13 }}>
                {a.name}{" "}
                <Text style={{ color: colors.foreground, fontWeight: "800" }}>
                  {formatAmount(a.balance, currency)}
                </Text>
              </Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}
