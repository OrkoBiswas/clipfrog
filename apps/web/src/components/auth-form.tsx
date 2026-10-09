"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  LoaderCircle,
  LockKeyhole,
  Mail,
  Scissors,
} from "lucide-react";
import { api } from "@/lib/api";
import "./account-pages.css";

type AuthMode =
  "login" | "register" | "forgot-password" | "reset-password" | "verify-email";

const copy: Record<
  AuthMode,
  { title: string; description: string; action: string }
> = {
  login: {
    title: "Welcome back.",
    description: "Your next great clip is waiting. Sign in to your workspace.",
    action: "Sign in to ClipForge",
  },
  register: {
    title: "Make more of every moment.",
    description:
      "Create your account and turn long videos into content worth sharing.",
    action: "Create your account",
  },
  "forgot-password": {
    title: "Forgot your password?",
    description:
      "It happens. Enter your email and we’ll send you a link to reset it.",
    action: "Send reset link",
  },
  "reset-password": {
    title: "A fresh start.",
    description:
      "Choose a strong password to keep your creative workspace secure.",
    action: "Save new password",
  },
  "verify-email": {
    title: "One last step.",
    description:
      "Confirm your email address to finish setting up your ClipForge account.",
    action: "Verify email address",
  },
};

export function AuthForm({ mode }: { mode: AuthMode }) {
  const router = useRouter();
  const errorRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const content = copy[mode];

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    const data = Object.fromEntries(new FormData(event.currentTarget));
    if (mode === "reset-password" || mode === "verify-email")
      data.token =
        new URLSearchParams(window.location.search).get("token") ?? "";
    try {
      if ((mode === "reset-password" || mode === "verify-email") && !data.token)
        throw new Error(
          mode === "reset-password"
            ? "This reset link is incomplete. Request a new link to continue."
            : "Open the verification link from your email to continue.",
        );
      const result = await api<{ message?: string }>(`/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify(data),
      });
      if (mode === "login" || mode === "register") {
        router.push("/dashboard");
        router.refresh();
      } else {
        setMessage(result.message ?? "You’re all set.");
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong. Please try again.",
      );
      requestAnimationFrame(() => errorRef.current?.focus());
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="access-layout">
      <aside className="access-story">
        <Image
          className="access-story-image"
          src="/images/creator-studio.png"
          alt=""
          fill
          sizes="(max-width: 680px) 0px, 52vw"
        />
        <Link href="/" className="access-brand" aria-label="ClipForge home">
          <span>
            <Scissors size={22} aria-hidden="true" />
          </span>
          ClipForge<span className="access-brand-tag">STUDIO</span>
        </Link>
        <div className="access-story-content">
          <span className="account-kicker">
            <span className="access-status-dot" /> YOUR IDEAS, IN MOTION
          </span>
          <h2>
            Good stories
            <br />
            deserve
            <br />
            <span>another life.</span>
          </h2>
          <p>
            That one brilliant idea. The conversation that stays with you. Turn
            your long videos into moments worth sharing.
          </p>
        </div>
        <ol
          className="access-story-steps"
          aria-label="From video to shareable clip"
        >
          <li>
            <span>01</span>
            <div>
              Find the moment<small>Discover your highlights</small>
            </div>
          </li>
          <li>
            <span>02</span>
            <div>
              Make your cut<small>Frame, caption, create</small>
            </div>
          </li>
          <li>
            <span>03</span>
            <div>
              Share your story<small>Export for your audience</small>
            </div>
          </li>
        </ol>
      </aside>
      <main className="access-main">
        <Link href="/" className="access-mobile-brand">
          <Scissors size={22} aria-hidden="true" /> ClipForge
        </Link>
        <div className="access-card">
          <div className="access-card-icon">
            {mode === "verify-email" || mode === "forgot-password" ? (
              <Mail size={23} aria-hidden="true" />
            ) : (
              <Scissors size={23} aria-hidden="true" />
            )}
          </div>
          <p className="access-form-kicker">YOUR CREATIVE WORKSPACE</p>
          <h1>{content.title}</h1>
          <p className="access-description">{content.description}</p>
          {message ? (
            <div className="access-success" role="status">
              <CheckCircle2 size={28} aria-hidden="true" />
              <h2>
                {mode === "forgot-password"
                  ? "Check your inbox"
                  : "You’re all set"}
              </h2>
              <p>{message}</p>
              <Link className="button primary" href="/login">
                Back to sign in
                <ArrowRight size={16} aria-hidden="true" />
              </Link>
            </div>
          ) : (
            <form className="access-form" onSubmit={submit} aria-busy={busy}>
              {mode === "register" && (
                <label className="field" htmlFor="auth-name">
                  Your name
                  <input
                    id="auth-name"
                    name="name"
                    required
                    maxLength={100}
                    autoComplete="name"
                    placeholder="Alex Morgan"
                    disabled={busy}
                  />
                </label>
              )}
              {!["reset-password", "verify-email"].includes(mode) && (
                <label className="field" htmlFor="auth-email">
                  Email address
                  <input
                    id="auth-email"
                    name="email"
                    type="email"
                    required
                    autoComplete="email"
                    placeholder="you@example.com"
                    disabled={busy}
                  />
                </label>
              )}
              {!["forgot-password", "verify-email"].includes(mode) && (
                <div className="field">
                  <div className="access-label-row">
                    <label htmlFor="auth-password">Password</label>
                    {mode === "login" && (
                      <Link href="/forgot-password">Forgot password?</Link>
                    )}
                  </div>
                  <div className="access-password">
                    <input
                      id="auth-password"
                      name="password"
                      type={showPassword ? "text" : "password"}
                      required
                      minLength={mode === "login" ? undefined : 12}
                      maxLength={128}
                      autoComplete={
                        mode === "login" ? "current-password" : "new-password"
                      }
                      placeholder={
                        mode === "login"
                          ? "Enter your password"
                          : "Create a strong password"
                      }
                      aria-describedby={
                        mode === "login" ? undefined : "password-hint"
                      }
                      disabled={busy}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={
                        showPassword ? "Hide password" : "Show password"
                      }
                      aria-pressed={showPassword}
                    >
                      {showPassword ? (
                        <EyeOff size={18} aria-hidden="true" />
                      ) : (
                        <Eye size={18} aria-hidden="true" />
                      )}
                    </button>
                  </div>
                  {mode !== "login" && (
                    <small id="password-hint">
                      Use at least 12 characters. A few memorable words work
                      well.
                    </small>
                  )}
                </div>
              )}
              {error && (
                <div
                  ref={errorRef}
                  tabIndex={-1}
                  className="account-feedback account-feedback-error"
                  role="alert"
                >
                  {error}
                  {mode === "reset-password" && (
                    <Link href="/forgot-password">
                      Request a new reset link{" "}
                      <ArrowRight size={14} aria-hidden="true" />
                    </Link>
                  )}
                </div>
              )}
              <button
                type="submit"
                className="button primary access-submit"
                disabled={busy}
              >
                {busy ? (
                  <>
                    <LoaderCircle
                      className="account-spin"
                      size={18}
                      aria-hidden="true"
                    />
                    {mode === "login" ? "Signing you in…" : "Just a moment…"}
                  </>
                ) : (
                  <>
                    {content.action}
                    <ArrowRight size={17} aria-hidden="true" />
                  </>
                )}
              </button>
            </form>
          )}
          <div className="access-switch">
            {mode === "login" ? (
              <>
                <span>New to ClipForge?</span>
                <Link href="/register">
                  Create an account <ArrowRight size={14} aria-hidden="true" />
                </Link>
              </>
            ) : mode === "register" ? (
              <>
                <span>Already have an account?</span>
                <Link href="/login">Sign in</Link>
              </>
            ) : (
              !message && (
                <Link href="/login">
                  <ArrowLeft size={14} aria-hidden="true" /> Back to sign in
                </Link>
              )
            )}
          </div>
          <p className="access-security">
            <LockKeyhole size={13} aria-hidden="true" /> Your creativity. Your
            private workspace.
          </p>
        </div>
        <p className="access-main-footer">Make something worth sharing.</p>
      </main>
    </div>
  );
}
