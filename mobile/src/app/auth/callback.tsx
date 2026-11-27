import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useRef } from "react";

import { Loading } from "@/components/ui";
import { readCallbackParams } from "@/lib/auth-callback";
import { supabase } from "@/lib/supabase";

/**
 * Destino de `asistentegastos://auth/callback?code=…`: cambia el código por una sesión, como
 * `/auth/callback` en la web. El verificador PKCE quedó en el llavero al registrarse, así que
 * solo funciona si el correo se abre en el mismo teléfono.
 */
export default function AuthCallbackScreen() {
  const params = useLocalSearchParams();
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const outcome = readCallbackParams(params);
    if (outcome.kind === "error") {
      router.replace({ pathname: "/login", params: { error: "confirmacion" } });
      return;
    }
    supabase.auth
      .exchangeCodeForSession(outcome.code)
      .then(({ error }) =>
        error
          ? router.replace({ pathname: "/login", params: { error: "confirmacion" } })
          : router.replace("/"),
      )
      .catch(() => router.replace({ pathname: "/login", params: { error: "confirmacion" } }));
  }, [params]);

  return <Loading />;
}
