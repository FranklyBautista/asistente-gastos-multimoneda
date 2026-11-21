import { useQuery } from "@tanstack/react-query";

import { getLinkedUser } from "./queries";

/** Usuario del bot vinculado (null si falta /vincular); lo comparten todas las pestañas. */
export function useLinkedUser() {
  return useQuery({ queryKey: ["linked-user"], queryFn: getLinkedUser });
}
