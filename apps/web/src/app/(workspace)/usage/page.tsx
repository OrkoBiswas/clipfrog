import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  CalendarDays,
  Clock3,
  Film,
  HardDrive,
  Info,
  Sparkles,
} from "lucide-react";
import { serverApi } from "@/lib/server";
import "@/components/account-pages.css";

export type Usage = {
  plan: string;
  usage: Record<string, number>;
  allowance: Record<string, number | null>;
  period_start: string;
  billing_enabled: boolean;
  customer_portal_available: boolean;
  subscription_status: string;
  administrator: boolean;
};

const metrics: Record<
  string,
  { label: string; description: string; icon: typeof Clock3 }
> = {
  input_minutes: {
    label: "Source minutes",
    description: "Long-form video analyzed for highlights.",
    icon: Clock3,
  },
  render_minutes: {
    label: "Render minutes",
    description: "Finished clips brought to life.",
    icon: Film,
  },
  storage_bytes: {
    label: "Media storage",
    description: "Uploads and saved render revisions.",
    icon: HardDrive,
  },
};

export default async function UsagePage() {
  const data = await serverApi<Usage>("/usage");
  const periodDate = new Date(data.period_start);
  const renewalDate = new Date(
    Date.UTC(periodDate.getUTCFullYear(), periodDate.getUTCMonth() + 1, 1),
  );
  const formatDate = (date: Date) =>
    date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC",
    });
  return (
    <div className="account-page">
      <header className="page-head">
        <div>
          <p className="eyebrow">KEEP YOUR CREATIVITY FLOWING</p>
          <h1>Workspace usage</h1>
          <p>A clear view of what you’ve used and what’s available.</p>
        </div>
        <Link className="button secondary" href="/billing">
          Manage plan
          <ArrowUpRight size={16} aria-hidden="true" />
        </Link>
      </header>
      <div className="account-usage-period">
        <div>
          <CalendarDays size={19} aria-hidden="true" />
          <span>
            {formatDate(periodDate)} — {formatDate(renewalDate)}
            <small>Monthly processing period · UTC</small>
          </span>
        </div>
        <span className="account-label is-positive">
          {data.administrator
            ? "Administrator · Unlimited"
            : `${data.plan} plan`}
        </span>
      </div>
      <section
        className="account-usage-grid"
        aria-label="Current workspace usage"
      >
        {Object.entries(data.allowance).map(([metric, limit]) => {
          const detail = metrics[metric] ?? {
            label: metric.replaceAll("_", " "),
            description: "Your current workspace consumption.",
            icon: Sparkles,
          };
          const Icon = detail.icon;
          const raw = data.usage[metric] ?? 0;
          const divisor = metric === "storage_bytes" ? 1024 ** 3 : 1;
          const used = raw / divisor;
          const unit = metric === "storage_bytes" ? "GB" : "min";
          const percent =
            limit !== null && limit > 0 ? Math.round((raw / limit) * 100) : 0;
          const remaining =
            limit === null ? null : Math.max(0, (limit - raw) / divisor);
          return (
            <article key={metric} className="account-usage-card">
              <div className="account-usage-card-top">
                <span className="account-icon">
                  <Icon size={20} aria-hidden="true" />
                </span>
                <span className="account-label">
                  {limit === null ? "Unlimited" : `${percent}% used`}
                </span>
              </div>
              <h2>{detail.label}</h2>
              <p>{detail.description}</p>
              <div className="account-usage-value">
                <strong>
                  {used.toLocaleString("en-US", {
                    maximumFractionDigits: metric === "storage_bytes" ? 2 : 1,
                  })}
                </strong>
                <span>
                  {unit}
                  {limit === null
                    ? " used"
                    : ` / ${(limit / divisor).toLocaleString("en-US")} ${unit}`}
                </span>
              </div>
              {limit !== null ? (
                <>
                  <progress
                    aria-label={`${detail.label} used`}
                    max={Math.max(limit, 1)}
                    value={Math.min(raw, limit)}
                    className={percent >= 90 ? "account-usage-high" : ""}
                  />
                  <p className="account-usage-remaining">
                    {remaining?.toLocaleString("en-US", {
                      maximumFractionDigits: metric === "storage_bytes" ? 2 : 1,
                    })}{" "}
                    {unit} available
                    {percent >= 90 && (
                      <Link href="/billing">
                        View plans
                        <ArrowRight size={13} aria-hidden="true" />
                      </Link>
                    )}
                  </p>
                </>
              ) : (
                <div className="account-unlimited">
                  <span />
                  Create without a monthly limit
                </div>
              )}
            </article>
          );
        })}
      </section>
      <section className="account-usage-explainer">
        <span className="account-icon">
          <Info size={20} aria-hidden="true" />
        </span>
        <div>
          <h2>How your usage is counted</h2>
          <div className="account-explainer-grid">
            <div>
              <h3>Processing</h3>
              <p>
                Totals include minutes reserved for queued and running jobs.
                Failed or canceled jobs release those reservations.
              </p>
            </div>
            <div>
              <h3>Storage</h3>
              <p>
                Storage includes your original uploads and previous render
                revisions. It reflects what’s saved, and does not reset monthly.
              </p>
            </div>
            <div>
              <h3>Your next cycle</h3>
              <p>
                Monthly processing allowances renew on {formatDate(renewalDate)}{" "}
                at 00:00 UTC. Your projects stay right where you left them.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
