import type { Session } from "@supabase/supabase-js";
import { useQueryClient } from "@tanstack/react-query";
import { createContext, type ReactNode, useContext, useEffect, useState } from "react";

import { supabase } from "./supabase";

type AuthState = { session: Session | null; loading: boolean };

const AuthContext = createContext<AuthState>({ session: null, loading: true });

/** Sesión de Supabase guardada en el llavero; se restaura al abrir la app. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>({ session: null, loading: true });

  useEffect(() => {
    let active = true;
    supabase.auth
      .getSession()
      .then(({ data }) => active && setState({ session: data.session, loading: false }))
      .catch(() => active && setState({ session: null, loading: false }));
    const { data } = supabase.auth.onAuthStateChange((event, session) => {
      // Al salir no quedan datos de la cuenta anterior en memoria.
      if (event === "SIGNED_OUT") queryClient.clear();
      setState({ session, loading: false });
    });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, [queryClient]);

  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  return useContext(AuthContext);
}
