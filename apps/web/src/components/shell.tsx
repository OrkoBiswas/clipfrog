"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  ArrowRight,
  Bell,
  CheckCheck,
  ChevronRight,
  CircleHelp,
  CreditCard,
  Film,
  Folder,
  LayoutDashboard,
  LayoutTemplate,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Palette,
  Plus,
  Search,
  Settings,
  Scissors,
  ChartNoAxesColumn,
  CircleCheck,
  CircleAlert,
} from "lucide-react";
import { api, type Project, type User } from "@/lib/api";
import { Modal } from "@/components/ui/primitives";
import { ThemeControl } from "@/components/ui/theme-provider";
import { useToast } from "@/components/ui/toast";
import { MotionReveal } from "@/components/motion/reveal";

const navigation = [
  ["Dashboard", "/dashboard", LayoutDashboard],
  ["Projects", "/projects", Folder],
  ["Clips", "/clips", Film],
  ["Brand Kit", "/brand-kit", Palette],
  ["Templates", "/templates", LayoutTemplate],
  ["Usage", "/usage", ChartNoAxesColumn],
  ["Billing", "/billing", CreditCard],
  ["Settings", "/settings", Settings],
] as const;
type UsageSummary = {
  plan: string;
  usage: Record<string, number>;
  allowance: Record<string, number | null>;
  administrator: boolean;
};
type Notification = {
  id: string;
  title: string;
  description: string;
  href: string;
  failed: boolean;
  date: string;
};
type Job = {
  id: string;
  status: string;
  job_type: string;
  error_message: string | null;
  finished_at: string | null;
  started_at: string | null;
};
const activeStatuses = [
  "ANALYZING",
  "FINDING_HIGHLIGHTS",
  "RENDERING",
  "EXPORTING",
  "VALIDATING",
  "QUEUED",
  "UPLOADING",
  "CANCEL_REQUESTED",
];
const fuzzyMatch = (text: string, query: string) => {
  let cursor = 0;
  for (const character of text.toLowerCase())
    if (character === query[cursor]) cursor++;
  return cursor === query.length;
};

export function Shell({
  user,
  children,
}: {
  user: User;
  children: React.ReactNode;
}) {
  const path = usePathname();
  const router = useRouter();
  const { toast } = useToast();
  const [collapsed, setCollapsed] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [command, setCommand] = useState(false);
  const [query, setQuery] = useState("");
  const [selection, setSelection] = useState(0);
  const [panel, setPanel] = useState<
    "notifications" | "account" | "help" | null
  >(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [read, setRead] = useState<string[]>([]);
  const [cleared, setCleared] = useState<string[]>([]);
  const [activityError, setActivityError] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const [signingOut, setSigningOut] = useState(false);
  const current =
    path === "/projects/new"
      ? "New project"
      : (navigation.find(([, href]) => path === href)?.[0] ??
        (path.startsWith("/projects/")
          ? "Project details"
          : path === "/operations"
            ? "Operations"
            : "Workspace"));
  const initials = user.name
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
  const active = projects.filter((project) =>
    activeStatuses.includes(project.status),
  );
  useEffect(() => {
    const frame = requestAnimationFrame(() => {
      try {
        setCollapsed(localStorage.getItem("clipforge-sidebar") === "collapsed");
        const saved = JSON.parse(
          localStorage.getItem(`clipforge-notifications-${user.id}`) ?? "{}",
        );
        setRead(Array.isArray(saved.read) ? saved.read : []);
        setCleared(Array.isArray(saved.cleared) ? saved.cleared : []);
      } catch {
        /* Storage is optional. */
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [user.id]);
  useEffect(() => {
    let canceled = false;
    async function refresh() {
      if (document.hidden) return;
      try {
        const [projectData, usageData] = await Promise.all([
          api<Project[]>("/projects"),
          api<UsageSummary>("/usage"),
        ]);
        if (canceled) return;
        setProjects(projectData);
        setUsage(usageData);
        const groups = await Promise.all(
          projectData.slice(0, 8).map(async (project) => {
            const jobs = await api<Job[]>(`/projects/${project.id}/jobs`);
            return jobs
              .filter((job) =>
                ["SUCCEEDED", "FAILED", "CANCELED"].includes(job.status),
              )
              .slice(0, 3)
              .map((job) => ({
                id: `${job.id}-${job.status}`,
                title: `${job.job_type.replaceAll("_", " ").toLowerCase()} ${job.status === "SUCCEEDED" ? "completed" : job.status.toLowerCase()}`,
                description: job.error_message || project.name,
                href: `/projects/${project.id}`,
                failed: job.status === "FAILED",
                date: job.finished_at ?? job.started_at ?? project.updated_at,
              }));
          }),
        );
        if (!canceled) {
          setNotifications(
            groups
              .flat()
              .sort((a, b) => b.date.localeCompare(a.date))
              .slice(0, 20),
          );
          setActivityError(false);
        }
      } catch {
        if (!canceled) setActivityError(true);
      }
    }
    void refresh();
    const timer = setInterval(() => void refresh(), 30000);
    return () => {
      canceled = true;
      clearInterval(timer);
    };
  }, [path]);
  useEffect(() => {
    function shortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommand((value) => !value);
        setQuery("");
        setSelection(0);
      }
    }
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);
  useEffect(() => {
    if (command) searchRef.current?.focus();
  }, [command]);
  const commands = useMemo(
    () =>
      [
        {
          title: "Create project",
          href: "/projects/new",
          group: "Action",
          icon: Plus,
        },
        ...navigation.map(([title, href, icon]) => ({
          title,
          href,
          group: "Page",
          icon,
        })),
        ...projects.map((project) => ({
          title: project.name,
          href: `/projects/${project.id}`,
          group: "Project",
          icon: Folder,
        })),
      ]
        .filter((item) =>
          fuzzyMatch(item.title, query.toLowerCase().replace(/\s/g, "")),
        )
        .slice(0, 16),
    [projects, query],
  );
  function navigate(href: string) {
    setCommand(false);
    setMobile(false);
    setPanel(null);
    router.push(href);
  }
  function saveNotificationState(nextRead: string[], nextCleared = cleared) {
    setRead(nextRead);
    setCleared(nextCleared);
    try {
      localStorage.setItem(
        `clipforge-notifications-${user.id}`,
        JSON.stringify({
          read: nextRead.slice(-200),
          cleared: nextCleared.slice(-200),
        }),
      );
    } catch {
      /* Keep session state. */
    }
  }
  const visibleNotifications = notifications.filter(
    (item) => !cleared.includes(item.id),
  );
  const unread = visibleNotifications.filter(
    (item) => !read.includes(item.id),
  ).length;
  async function logout() {
    setSigningOut(true);
    try {
      await api("/auth/logout", { method: "POST" });
      router.push("/login");
      router.refresh();
    } catch (error) {
      toast(
        "Couldn’t sign out",
        error instanceof Error ? error.message : "Please try again.",
        "error",
      );
      setSigningOut(false);
    }
  }
  function navLink([label, href, Icon]: (typeof navigation)[number]) {
    const selected =
      path === href ||
      (href === "/projects" &&
        path.startsWith("/projects/") &&
        path !== "/projects/new");
    return (
      <Link
        key={href}
        href={href}
        onClick={() => setMobile(false)}
        title={collapsed ? label : undefined}
        aria-current={selected ? "page" : undefined}
        className={`nav-link ${selected ? "active" : ""}`}
      >
        <Icon aria-hidden="true" />
        <span className="nav-text">{label}</span>
      </Link>
    );
  }
  const nav = (
    <>
      <Link
        href="/projects/new"
        onClick={() => setMobile(false)}
        className="button sidebar-create"
        title={collapsed ? "New project" : undefined}
      >
        <Plus size={17} />
        <span className="nav-text">New Project</span>
      </Link>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Main navigation" className="nav-section">
        {navigation.slice(0, 5).map(navLink)}
      </nav>
      <div className="nav-label">MANAGE</div>
      <nav aria-label="Account navigation" className="nav-section">
        {navigation.slice(5).map(navLink)}
        {user.is_admin && (
          <Link
            className={`nav-link ${path === "/operations" ? "active" : ""}`}
            aria-current={path === "/operations" ? "page" : undefined}
            href="/operations"
            onClick={() => setMobile(false)}
            title="Operations"
          >
            <Activity aria-hidden="true" />
            <span className="nav-text">Operations</span>
          </Link>
        )}
      </nav>
    </>
  );
  return (
    <div className={`shell ${collapsed ? "sidebar-collapsed" : ""}`}>
      <a href="#main" className="skip">
        Skip to content
      </a>
      <aside className="sidebar" aria-label="Workspace sidebar">
        <Link
          className="brand sidebar-brand"
          href="/dashboard"
          aria-label="ClipForge dashboard"
        >
          <span className="brand-mark">
            <Scissors aria-hidden="true" />
          </span>
          <span className="brand-word">
            ClipForge <small>AI</small>
          </span>
        </Link>
        {nav}
        <div className="sidebar-bottom">
          {usage && (
            <div className="sidebar-usage">
              <strong>
                {usage.administrator
                  ? "Administrator workspace"
                  : `${usage.plan.charAt(0).toUpperCase() + usage.plan.slice(1)} plan`}
              </strong>
              <small>
                {usage.allowance.input_minutes == null
                  ? "Unlimited processing minutes"
                  : `${Math.round(usage.usage.input_minutes ?? 0)} of ${usage.allowance.input_minutes} minutes used`}
              </small>
              {usage.allowance.input_minutes != null && (
                <progress
                  aria-label="Processing minutes used"
                  max={usage.allowance.input_minutes || 1}
                  value={usage.usage.input_minutes ?? 0}
                />
              )}
              <Link className="text-button" href="/usage">
                View usage <ArrowRight size={12} />
              </Link>
            </div>
          )}
          <div className="account">
            <button
              className="avatar"
              aria-label="Open account menu"
              title={user.name}
              onClick={() => setPanel("account")}
            >
              {initials}
            </button>
            <div className="account-copy">
              <strong>{user.name}</strong>
              <small>{user.email}</small>
            </div>
            <button
              className="icon-button"
              aria-label="Sign out"
              disabled={signingOut}
              onClick={() => void logout()}
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="icon-button desktop-collapse"
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-expanded={!collapsed}
              onClick={() => {
                setCollapsed(!collapsed);
                try {
                  localStorage.setItem(
                    "clipforge-sidebar",
                    !collapsed ? "collapsed" : "expanded",
                  );
                } catch {}
              }}
            >
              {collapsed ? (
                <PanelLeftOpen size={17} />
              ) : (
                <PanelLeftClose size={17} />
              )}
            </button>
            <button
              className="icon-button mobile-menu-button"
              aria-label="Open navigation"
              aria-expanded={mobile}
              onClick={() => setMobile(true)}
            >
              <Menu size={20} />
            </button>
            <nav className="breadcrumb" aria-label="Breadcrumb">
              <span>Workspace</span>
              <ChevronRight size={12} />
              <strong>{current}</strong>
            </nav>
          </div>
          <div className="topbar-right">
            <button
              className="search-trigger"
              onClick={() => {
                setQuery("");
                setSelection(0);
                setCommand(true);
              }}
              aria-label="Search workspace"
            >
              <Search size={14} />
              <span>Search anything…</span>
              <kbd>⌘ K</kbd>
            </button>
            {active.length > 0 && (
              <Link
                className="icon-button"
                href={`/projects/${active[0].id}`}
                aria-label={`${active.length} projects processing`}
                title={`${active.length} projects processing`}
              >
                <Activity size={17} />
              </Link>
            )}
            <span className="topbar-divider" />
            <button
              className="icon-button"
              aria-label="Help and shortcuts"
              title="Help and shortcuts"
              onClick={() => setPanel("help")}
            >
              <CircleHelp size={17} />
            </button>
            <button
              className="icon-button notification-trigger"
              aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
              title="Notifications"
              onClick={() => setPanel("notifications")}
            >
              <Bell size={17} />
              {unread > 0 && <i />}
            </button>
            <button
              className="avatar"
              aria-label="Open account menu"
              onClick={() => setPanel("account")}
            >
              {initials}
            </button>
          </div>
        </header>
        <main id="main" className="content" tabIndex={-1}>
          <MotionReveal>{children}</MotionReveal>
        </main>
      </div>
      <Modal
        open={mobile}
        onClose={() => setMobile(false)}
        title="ClipForge"
        className="mobile-navigation"
      >
        <div className="mobile-nav-content">{nav}</div>
        <div className="account">
          <span className="avatar">{initials}</span>
          <div className="account-copy">
            <strong>{user.name}</strong>
            <small>{user.email}</small>
          </div>
          <button
            className="icon-button"
            aria-label="Sign out"
            onClick={() => void logout()}
          >
            <LogOut size={17} />
          </button>
        </div>
      </Modal>
      <Modal
        open={command}
        onClose={() => setCommand(false)}
        title="Search workspace"
        className="command-dialog"
      >
        <div className="command-search">
          <Search size={20} aria-hidden="true" />
          <input
            ref={searchRef}
            placeholder="Find a project or jump to a page…"
            aria-label="Search projects and pages"
            role="combobox"
            aria-expanded="true"
            aria-controls="command-results"
            aria-activedescendant={
              commands.length ? `command-${selection}` : undefined
            }
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelection(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                e.preventDefault();
                const next = commands.length
                  ? (selection +
                      (e.key === "ArrowDown" ? 1 : commands.length - 1)) %
                    commands.length
                  : 0;
                setSelection(next);
                document
                  .getElementById(`command-${next}`)
                  ?.scrollIntoView({ block: "nearest" });
              }
              if (e.key === "Enter" && commands[selection]) {
                e.preventDefault();
                navigate(commands[selection].href);
              }
            }}
          />
        </div>
        <div
          role="listbox"
          id="command-results"
          aria-label="Search results"
          className="command-results"
        >
          {commands.map((item, i) => (
            <button
              type="button"
              role="option"
              aria-selected={i === selection}
              tabIndex={-1}
              className="command-result"
              id={`command-${i}`}
              key={item.href}
              onMouseMove={() => setSelection(i)}
              onClick={() => navigate(item.href)}
            >
              <item.icon size={17} />
              <span>{item.title}</span>
              <small>{item.group}</small>
            </button>
          ))}
          {commands.length === 0 && (
            <div className="empty">
              <h3>No results found</h3>
              <p>Try a project name or a page like Templates.</p>
            </div>
          )}
        </div>
        <div className="command-foot">
          <span>↑ ↓ to navigate</span>
          <span>↵ to open</span>
          <span>esc to close</span>
        </div>
      </Modal>
      <Modal
        open={panel === "notifications"}
        onClose={() => setPanel(null)}
        title="Notifications"
      >
        <div className="section-head">
          <small>Activity from your recent projects</small>
          <button
            className="text-button"
            disabled={!unread}
            onClick={() =>
              saveNotificationState([
                ...new Set([...read, ...notifications.map((item) => item.id)]),
              ])
            }
          >
            <CheckCheck size={14} />
            Mark all read
          </button>
        </div>
        {activityError && (
          <p className="form-error" role="alert">
            Activity couldn’t refresh. It will retry automatically.
          </p>
        )}
        {visibleNotifications.length ? (
          visibleNotifications.map((item) => (
            <Link
              href={item.href}
              key={item.id}
              className={`activity-item ${read.includes(item.id) ? "" : "unread"}`}
              onClick={() => {
                saveNotificationState([...new Set([...read, item.id])]);
                setPanel(null);
              }}
            >
              {item.failed ? (
                <CircleAlert size={19} />
              ) : (
                <CircleCheck size={19} />
              )}
              <div>
                <strong style={{ textTransform: "capitalize" }}>
                  {item.title}
                </strong>
                <p>{item.description}</p>
                <div className="activity-meta">
                  <small>{new Date(item.date).toLocaleDateString()}</small>
                  <span className="text-button">
                    Open project <ArrowRight size={12} />
                  </span>
                </div>
              </div>
            </Link>
          ))
        ) : (
          <div className="empty">
            <Bell size={30} />
            <h3>You’re all caught up</h3>
            <p>Processing and render updates will appear here.</p>
          </div>
        )}
        {visibleNotifications.length > 0 && (
          <button
            className="text-button"
            onClick={() =>
              saveNotificationState(read, [
                ...new Set([
                  ...cleared,
                  ...notifications.map((item) => item.id),
                ]),
              ])
            }
          >
            Clear notifications
          </button>
        )}
      </Modal>
      <Modal
        open={panel === "account"}
        onClose={() => setPanel(null)}
        title={user.name}
      >
        <p>{user.email}</p>
        <div className="account-menu-links">
          <Link href="/settings" onClick={() => setPanel(null)}>
            <Settings size={18} />
            Account settings
          </Link>
          <Link href="/billing" onClick={() => setPanel(null)}>
            <CreditCard size={18} />
            Plan and billing
          </Link>
        </div>
        <hr />
        <p className="eyebrow">Appearance</p>
        <ThemeControl />
        <hr />
        <button
          className="button secondary"
          disabled={signingOut}
          onClick={() => void logout()}
        >
          <LogOut size={16} />
          {signingOut ? "Signing out…" : "Sign out"}
        </button>
      </Modal>
      <Modal
        open={panel === "help"}
        onClose={() => setPanel(null)}
        title="A little help, when you need it"
      >
        <p>
          Upload a video, choose your clip settings, then find and refine its
          strongest moments.
        </p>
        <div className="account-menu-links">
          <Link href="/projects/new" onClick={() => setPanel(null)}>
            <Plus size={18} />
            Create a project
          </Link>
          <Link href="/templates" onClick={() => setPanel(null)}>
            <LayoutTemplate size={18} />
            Explore caption styles
          </Link>
        </div>
        <hr />
        <h3>Keyboard shortcuts</h3>
        <dl className="meta-grid">
          <div>
            <dt>Search workspace</dt>
            <dd>⌘ / Ctrl + K</dd>
          </div>
          <div>
            <dt>Close dialog</dt>
            <dd>Esc</dd>
          </div>
          <div>
            <dt>Move between controls</dt>
            <dd>Tab</dd>
          </div>
        </dl>
        <p className="muted">
          In the clip editor, use ⌘ / Ctrl + S to save. Playback shortcuts work
          when the preview is focused.
        </p>
      </Modal>
    </div>
  );
}
