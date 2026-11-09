/** Login, registro y vinculación: una columna angosta, sin el menú del panel. */
export default function AccountLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col px-5 py-10">{children}</main>
  );
}
