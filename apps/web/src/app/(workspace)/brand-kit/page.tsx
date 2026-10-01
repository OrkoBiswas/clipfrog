import { BrandKits, type BrandKit } from "@/components/brand-kits";
import { serverApi } from "@/lib/server";

export default async function BrandKitPage() {
  const kits = await serverApi<BrandKit[]>("/brand-kits");
  return <BrandKits initial={kits} />;
}
