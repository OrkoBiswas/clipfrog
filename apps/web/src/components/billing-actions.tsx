"use client";

import { useState } from "react";
import {
  ArrowRight,
  Check,
  CreditCard,
  ExternalLink,
  Info,
  LoaderCircle,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import "./account-pages.css";

const plans = [
  {
    id: "free",
    name: "Free",
    description: "Find your first great moments.",
    source: "60",
    render: "30",
    storage: "5",
  },
  {
    id: "creator",
    name: "Creator",
    description: "Build a consistent content rhythm.",
    source: "600",
    render: "300",
    storage: "50",
  },
  {
    id: "pro",
    name: "Pro",
    description: "More stories. More room to grow.",
    source: "2,400",
    render: "1,200",
    storage: "200",
  },
];

export function BillingActions({
  enabled,
  portal,
  currentPlan = "free",
  administrator = false,
}: {
  enabled: boolean;
  portal: boolean;
  currentPlan?: string;
  administrator?: boolean;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  async function open(plan?: string) {
    if (busy) return;
    setBusy(plan ?? "portal");
    setError("");
    try {
      const result = await api<{ url: string }>(
        plan ? "/billing/checkout" : "/billing/portal",
        {
          method: "POST",
          ...(plan ? { body: JSON.stringify({ plan }) } : {}),
        },
      );
      window.location.assign(result.url);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Billing is unavailable. Please try again.",
      );
      setBusy(null);
    }
  }
  return (
    <>
      {!administrator && (
        <>
          <div className="account-section-heading">
            <h2>A little more room to create</h2>
            <p>
              Pick the allowance that fits your workflow. Every plan includes
              the core editing experience.
            </p>
          </div>
          <div className="account-plan-grid">
            {plans.map((plan) => {
              const current = currentPlan === plan.id;
              return (
                <article
                  className={`account-plan-card ${plan.id === "creator" ? "is-featured" : ""}`}
                  key={plan.id}
                >
                  <div className="account-plan-top">
                    <h3>{plan.name}</h3>
                    {current ? (
                      <span className="account-label is-positive">
                        <Check size={13} aria-hidden="true" /> Current plan
                      </span>
                    ) : plan.id === "creator" ? (
                      <span className="account-label">
                        <Sparkles size={12} aria-hidden="true" /> Keep creating
                      </span>
                    ) : null}
                  </div>
                  <p>{plan.description}</p>
                  <div className="account-plan-allowance">
                    <strong>{plan.source}</strong>
                    <span>source minutes / month</span>
                  </div>
                  <ul>
                    <li>
                      <Check size={15} aria-hidden="true" />
                      <span>
                        <strong>{plan.render}</strong> render minutes / month
                      </span>
                    </li>
                    <li>
                      <Check size={15} aria-hidden="true" />
                      <span>
                        <strong>{plan.storage} GB</strong> media storage
                      </span>
                    </li>
                    <li>
                      <Check size={15} aria-hidden="true" />
                      <span>Highlights, captions & clip editor</span>
                    </li>
                  </ul>
                  <div className="account-plan-footer">
                    {current ? (
                      <div className="account-plan-current">
                        <Check size={16} aria-hidden="true" />
                        Your current plan
                      </div>
                    ) : plan.id === "free" ? (
                      <p>Included with every new account</p>
                    ) : (
                      <button
                        className={`button ${plan.id === "creator" ? "primary" : "secondary"}`}
                        disabled={!enabled || busy !== null}
                        onClick={() => open(plan.id)}
                      >
                        {busy === plan.id ? (
                          <>
                            <LoaderCircle
                              className="account-spin"
                              size={16}
                              aria-hidden="true"
                            />
                            Opening checkout…
                          </>
                        ) : (
                          <>
                            Choose {plan.name}
                            <ArrowRight size={16} aria-hidden="true" />
                          </>
                        )}
                      </button>
                    )}
                    <small>
                      {plan.id === "free"
                        ? "No subscription required"
                        : "Price and terms shown at checkout"}
                    </small>
                  </div>
                </article>
              );
            })}
          </div>
          {!enabled && (
            <div className="account-info-box">
              <Info size={20} aria-hidden="true" />
              <div>
                <strong>
                  Paid plans aren’t available on this workspace yet
                </strong>
                <p>
                  You can keep creating on your current plan. Checkout will be
                  available once billing is connected.
                </p>
              </div>
            </div>
          )}
        </>
      )}
      {portal && (
        <section className="account-billing-portal">
          <span className="account-icon">
            <CreditCard size={21} aria-hidden="true" />
          </span>
          <div>
            <h3>Subscription & payment details</h3>
            <p>
              Manage your plan, payment method, and invoices in the secure
              billing portal.
            </p>
          </div>
          <button
            className="button secondary"
            disabled={busy !== null}
            onClick={() => open()}
          >
            {busy === "portal" ? (
              <LoaderCircle
                className="account-spin"
                size={16}
                aria-hidden="true"
              />
            ) : (
              <ExternalLink size={16} aria-hidden="true" />
            )}
            {busy === "portal" ? "Opening portal…" : "Manage subscription"}
          </button>
        </section>
      )}
      {error && (
        <div className="account-feedback account-feedback-error" role="alert">
          {error}
        </div>
      )}
    </>
  );
}
