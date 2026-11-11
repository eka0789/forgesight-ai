import { AuthShell } from "@/components/layout/auth-shell";

// All app pages are client-rendered against a live API — skip static prerender.
export const dynamic = "force-dynamic";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthShell>{children}</AuthShell>;
}
