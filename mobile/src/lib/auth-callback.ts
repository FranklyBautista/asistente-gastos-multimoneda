/** Ruta de la app a la que vuelve el enlace de confirmación del correo. */
export const AUTH_CALLBACK_PATH = "auth/callback";

type Params = Record<string, string | string[] | undefined>;

export type CallbackOutcome = { kind: "code"; code: string } | { kind: "error" };

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/**
 * Lee lo que Supabase agrega al volver del correo: `?code=` (flujo PKCE) si se pudo confirmar,
 * o `?error=…&error_code=otp_expired` si el enlace venció o ya se usó.
 */
export function readCallbackParams(params: Params): CallbackOutcome {
  const code = first(params.code);
  if (first(params.error) || first(params.error_code) || !code) return { kind: "error" };
  return { kind: "code", code };
}
