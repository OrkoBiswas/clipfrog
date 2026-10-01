import Link from "next/link";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { serverApi } from "@/lib/server";
import type { User } from "@/lib/api";
import {
  OperationsPanel,
  type OperationsData,
} from "@/components/operations-panel";

export default async function OperationsPage() {
  const user = await serverApi<User>("/me");
  if (!user.is_admin)
    return (
      <section className="account-access-denied">
        <span className="account-icon">
          <ShieldCheck size={28} aria-hidden="true" />
        </span>
        <h1>Administrator access required</h1>
        <p>
          This area is available to workspace administrators. Your projects are
          ready in your dashboard.
        </p>
        <Link href="/dashboard" className="button secondary">
          <ArrowLeft size={16} aria-hidden="true" />
          Back to dashboard
        </Link>
      </section>
    );
  const data = await serverApi<OperationsData>("/operations");
  return <OperationsPanel initialData={data} />;
}
