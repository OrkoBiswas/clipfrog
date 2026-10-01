"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  CheckCircle2,
  KeyRound,
  LoaderCircle,
  Mail,
  Monitor,
  Palette,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { api } from "@/lib/api";
import { ThemeControl } from "@/components/ui/theme-provider";
import "./account-pages.css";

const tabs = [
  { id: "profile", label: "Profile", icon: UserRound },
  { id: "security", label: "Security", icon: ShieldCheck },
  { id: "appearance", label: "Appearance", icon: Palette },
] as const;
type Tab = (typeof tabs)[number]["id"];

export function AccountSettings({
  name,
  email,
  verified,
}: {
  name: string;
  email: string;
  verified: boolean;
}) {
  const [activeTab, setActiveTab] = useState<Tab>("profile");
  const [feedback, setFeedback] = useState<{
    text: string;
    error: boolean;
  } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  async function send(path: string, body?: object) {
    if (busy) return;
    setBusy(path);
    setFeedback(null);
    try {
      const result = await api<{ message: string }>(path, {
        method: "POST",
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      setFeedback({ text: result.message, error: false });
    } catch (error) {
      setFeedback({
        text:
          error instanceof Error
            ? error.message
            : "Request failed. Please try again.",
        error: true,
      });
    } finally {
      setBusy(null);
    }
  }
  return (
    <div className="account-settings-layout">
      <div
        className="account-tabs"
        role="tablist"
        aria-label="Account settings"
      >
        {tabs.map(({ id, label, icon: Icon }, index) => (
          <button
            key={id}
            type="button"
            ref={(node) => {
              tabRefs.current[index] = node;
            }}
            role="tab"
            id={`settings-tab-${id}`}
            aria-selected={activeTab === id}
            aria-controls={`settings-panel-${id}`}
            tabIndex={activeTab === id ? 0 : -1}
            onClick={() => {
              setActiveTab(id);
              setFeedback(null);
            }}
            onKeyDown={(event) => {
              const next =
                event.key === "ArrowRight"
                  ? (index + 1) % tabs.length
                  : event.key === "ArrowLeft"
                    ? (index + tabs.length - 1) % tabs.length
                    : event.key === "Home"
                      ? 0
                      : event.key === "End"
                        ? tabs.length - 1
                        : null;
              if (next !== null) {
                event.preventDefault();
                setActiveTab(tabs[next].id);
                setFeedback(null);
                tabRefs.current[next]?.focus();
              }
            }}
          >
            <Icon size={17} aria-hidden="true" />
            {label}
          </button>
        ))}
      </div>
      <section
        className="account-settings-panel"
        role="tabpanel"
        id={`settings-panel-${activeTab}`}
        aria-labelledby={`settings-tab-${activeTab}`}
        tabIndex={0}
      >
        {activeTab === "profile" && (
          <>
            <div className="account-section-heading">
              <h2>Your profile</h2>
              <p>The details associated with your ClipForge account.</p>
            </div>
            <div className="account-profile-identity">
              <span className="account-profile-avatar">
                {name.trim().charAt(0).toUpperCase() ||
                  email.charAt(0).toUpperCase()}
              </span>
              <div>
                <h3>{name}</h3>
                <p>{email}</p>
              </div>
              <span
                className={`account-label ${verified ? "is-positive" : ""}`}
              >
                {verified ? (
                  <>
                    <CheckCircle2 size={13} aria-hidden="true" /> Verified
                  </>
                ) : (
                  "Verification pending"
                )}
              </span>
            </div>
            <dl className="account-profile-fields">
              <div>
                <dt>Full name</dt>
                <dd>{name}</dd>
              </div>
              <div>
                <dt>Email address</dt>
                <dd>{email}</dd>
              </div>
            </dl>
            {!verified && (
              <div className="account-info-box">
                <Mail size={20} aria-hidden="true" />
                <div>
                  <strong>Verify your email address</strong>
                  <p>
                    Check your inbox for a verification link, or send yourself a
                    new one.
                  </p>
                  <button
                    className="button secondary"
                    disabled={busy !== null}
                    onClick={() => send("/auth/verification-email")}
                  >
                    {busy === "/auth/verification-email" ? (
                      <LoaderCircle
                        className="account-spin"
                        size={15}
                        aria-hidden="true"
                      />
                    ) : (
                      <Mail size={15} aria-hidden="true" />
                    )}
                    Resend verification email
                  </button>
                </div>
              </div>
            )}
            <div className="account-inline-link">
              <span>Looking for your subscription details?</span>
              <Link href="/billing">
                Manage your plan
                <ArrowUpRight size={15} aria-hidden="true" />
              </Link>
            </div>
          </>
        )}
        {activeTab === "security" && (
          <>
            <div className="account-section-heading">
              <h2>Account security</h2>
              <p>Keep access to your workspace in your hands.</p>
            </div>
            <div className="account-setting-row">
              <span className="account-icon">
                <KeyRound size={20} aria-hidden="true" />
              </span>
              <div>
                <h3>Password</h3>
                <p>We’ll send a secure password reset link to {email}.</p>
              </div>
              <button
                className="button secondary"
                disabled={busy !== null}
                onClick={() => send("/auth/forgot-password", { email })}
              >
                {busy === "/auth/forgot-password" && (
                  <LoaderCircle
                    className="account-spin"
                    size={15}
                    aria-hidden="true"
                  />
                )}
                {busy === "/auth/forgot-password"
                  ? "Sending link…"
                  : "Reset password"}
              </button>
            </div>
            <div className="account-setting-row">
              <span className="account-icon">
                <Mail size={20} aria-hidden="true" />
              </span>
              <div>
                <h3>Email verification</h3>
                <p>
                  {verified
                    ? "Your email address is verified."
                    : "Confirm your email to secure your account."}
                </p>
              </div>
              {verified ? (
                <span className="account-label is-positive">
                  <CheckCircle2 size={14} aria-hidden="true" /> Verified
                </span>
              ) : (
                <button
                  className="button secondary"
                  disabled={busy !== null}
                  onClick={() => send("/auth/verification-email")}
                >
                  {busy === "/auth/verification-email"
                    ? "Sending…"
                    : "Send verification"}
                </button>
              )}
            </div>
          </>
        )}
        {activeTab === "appearance" && (
          <>
            <div className="account-section-heading">
              <h2>Make yourself at home</h2>
              <p>Choose the look that feels right for your workspace.</p>
            </div>
            <div className="account-appearance">
              <div className="account-setting-row">
                <span className="account-icon">
                  <Monitor size={20} aria-hidden="true" />
                </span>
                <div>
                  <h3>Interface theme</h3>
                  <p>
                    Choose light, dark, or match your device. Your preference is
                    saved in this browser.
                  </p>
                </div>
              </div>
              <ThemeControl />
            </div>
            <div className="account-info-box">
              <Palette size={20} aria-hidden="true" />
              <div>
                <strong>Your workspace, consistently styled</strong>
                <p>
                  Your theme applies across projects, the editor, and account
                  pages. Motion follows your device’s accessibility preferences.
                </p>
              </div>
            </div>
          </>
        )}
        {feedback && (
          <div
            className={`account-feedback ${feedback.error ? "account-feedback-error" : "account-feedback-success"}`}
            role={feedback.error ? "alert" : "status"}
          >
            {!feedback.error && <CheckCircle2 size={17} aria-hidden="true" />}
            {feedback.text}
          </div>
        )}
      </section>
    </div>
  );
}
