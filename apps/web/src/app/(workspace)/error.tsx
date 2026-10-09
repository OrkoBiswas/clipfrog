"use client";
import Link from "next/link";
import { ArrowLeft, RefreshCw, Unplug } from "lucide-react";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <section className="panel workspace-error">
      <span className="workspace-error-icon">
        <Unplug size={28} aria-hidden="true" />
      </span>
      <p className="eyebrow">LET’S GET YOU BACK TO CREATING</p>
      <h1>We couldn’t load this page</h1>
      <p>
        Try again in a moment. If this keeps happening, check your connection.
      </p>
      <div className="actions">
        <Link className="button secondary" href="/dashboard">
          <ArrowLeft size={16} />
          Back to your studio
        </Link>
        <button className="button" onClick={reset}>
          <RefreshCw size={16} aria-hidden="true" />
          Try again
        </button>
      </div>
    </section>
  );
}
