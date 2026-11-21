import { authErrorMessage } from "../auth-errors";
import { formatAmount, formatUsd } from "../format";
import { CODE_PATTERN, linkErrorMessage, normalizeCode } from "../link-errors";

test("los montos usan los decimales de cada moneda, como el bot", () => {
  expect(formatAmount(20000, "COP")).toBe("20.000");
  expect(formatAmount(49250.5, "VES")).toBe("49.250,50");
  expect(formatUsd(-5.66)).toBe("−$5,66");
});

test("el código de /vincular se normaliza y valida como en la web", () => {
  expect(normalizeCode(" abcd-2345 ")).toBe("ABCD2345");
  expect(CODE_PATTERN.test("ABCD2345")).toBe(true);
  expect(CODE_PATTERN.test("ABCD0145")).toBe(false); // sin 0 ni 1
  expect(linkErrorMessage("invalid_code")).toMatch(/no es válido/);
  expect(linkErrorMessage("algo raro")).toMatch(/No se pudo vincular/);
});

test("los errores de sesión no muestran detalles internos", () => {
  expect(authErrorMessage("invalid_credentials", "signIn")).toBe(
    "Correo o contraseña incorrectos.",
  );
  expect(authErrorMessage("email_not_confirmed", "signIn")).toMatch(/Confirma tu correo/);
  expect(authErrorMessage("weak_password", "signUp")).toMatch(/muy débil/);
});
