import { Redirect, Stack } from "expo-router";

import { Loading } from "@/components/ui";
import { useAuth } from "@/lib/auth";

/** Login y registro: con sesión iniciada no tiene sentido verlos. */
export default function AccountLayout() {
  const { session, loading } = useAuth();
  if (loading) return <Loading />;
  if (session) return <Redirect href="/" />;
  return <Stack screenOptions={{ headerShown: false }} />;
}
