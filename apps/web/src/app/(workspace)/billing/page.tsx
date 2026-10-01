import Link from "next/link";
import {
  ArrowUpRight,
  CalendarDays,
  CheckCircle2,
  ShieldCheck,
} from "lucide-react";
import { serverApi } from "@/lib/server";
import { BillingActions } from "@/components/billing-actions";
import type { Usage } from "../usage/page";
import "@/components/account-pages.css";

export default async function BillingPage() {
  const data = await serverApi<Usage>("/usage");
  return (
    <div className="account-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">ROOM FOR YOUR NEXT BIG IDEA</p>
          <h1>Plans & billing</h1>
          <p>A plan that keeps up with your creativity.</p>
        </div>
        <Link className="button secondary" href="/usage">
          View usage
          <ArrowUpRight size={16} aria-hidden="true" />
        </Link>
      </header>
      <section className="account-plan-summary">
        <div className="account-summary-icon">
          {data.administrator ? (
            <ShieldCheck size={24} aria-hidden="true" />
          ) : (
            <CheckCircle2 size={24} aria-hidden="true" />
          )}
        </div>
        <div>
          <span className="account-kicker">YOUR CURRENT PLAN</span>
          <h2>
            {data.administrator ? "Administrator" : data.plan}
            <span className="account-label">
              {data.administrator
                ? "Unlimited access"
                : data.subscription_status.replaceAll("_", " ")}
            </span>
          </h2>
          <p>
            {data.administrator
              ? "Unlimited source minutes, rendering, and media storage."
              : "Your allowance is ready when inspiration strikes."}
          </p>
        </div>
        <div className="account-renewal">
          <CalendarDays size={18} aria-hidden="true" />
          <span>
            Processing allowance
            <br />
            <strong>
              {data.administrator
                ? "No monthly limits"
                : "Renews monthly · UTC"}
            </strong>
          </span>
        </div>
      </section>
      <BillingActions
        enabled={data.billing_enabled}
        portal={data.customer_portal_available}
        currentPlan={data.plan}
        administrator={data.administrator}
      />
      {!data.administrator && (
        <p className="account-billing-note">
          <ShieldCheck size={16} aria-hidden="true" />
          Processing allowances renew each calendar month in UTC. Plan changes
          take effect after payment confirmation. Prices and payment terms are
          always shown before you pay.
        </p>
      )}
    </div>
  );
}
