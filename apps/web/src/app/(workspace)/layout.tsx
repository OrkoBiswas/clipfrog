import { getUser } from "@/lib/server";
import { Shell } from "@/components/shell";
import { CaptionLibraryProvider } from "@/components/caption-library";
export default async function Layout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getUser();
  return (
    <CaptionLibraryProvider userId={user.id}>
      <Shell user={user}>{children}</Shell>
    </CaptionLibraryProvider>
  );
}
