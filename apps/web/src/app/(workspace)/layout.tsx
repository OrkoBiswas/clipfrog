import { getUser } from "@/lib/server";
import { Shell } from "@/components/shell";
export default async function Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getUser();
  return <Shell user={user}>{children}</Shell>;
}
