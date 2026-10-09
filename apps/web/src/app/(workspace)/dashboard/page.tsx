import Link from "next/link";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  AudioLines,
  Clock3,
  Film,
  Folder,
  HardDrive,
  Palette,
  Plus,
  Scissors,
  Upload,
} from "lucide-react";
import { getUser, ServerApiError, serverApi } from "@/lib/server";
import type { Project, Stats } from "@/lib/api";
import { ProjectsList } from "@/components/projects-list";
import { StatusBadge } from "@/components/ui/primitives";
import {
  DashboardOnboarding,
  RecentClips,
} from "@/components/dashboard-extras";
import { StudioShowcase } from "@/components/studio-showcase";
import type { Clip } from "@/components/clips-panel";

export default async function Dashboard() {
  const [user, projects, stats] = await Promise.all([
    getUser(),
    serverApi<Project[]>("/projects"),
    serverApi<Stats>("/dashboard"),
  ]);
  const groups = await Promise.all(
    projects.slice(0, 4).map(async (project) => {
      try {
        return {
          project,
          clips: await serverApi<Clip[]>(`/projects/${project.id}/clips`),
        };
      } catch (error) {
        if (error instanceof ServerApiError && error.status === 404)
          return { project, clips: [] };
        throw error;
      }
    }),
  );
  const recent = groups
    .flatMap((group) =>
      group.clips.slice(0, 2).map((clip) => ({ clip, project: group.project })),
    )
    .slice(0, 3);
  const active = projects.filter((project) =>
    [
      "ANALYZING",
      "FINDING_HIGHLIGHTS",
      "RENDERING",
      "EXPORTING",
      "VALIDATING",
      "QUEUED",
      "UPLOADING",
    ].includes(project.status),
  );
  const metrics = [
    {
      label: "Your projects",
      value: stats.projects,
      note: "Ideas in motion",
      icon: Folder,
    },
    {
      label: "Clips created",
      value: stats.clips_created,
      note: "From long-form to standout",
      icon: Film,
    },
    {
      label: "Minutes processed",
      value: stats.minutes_processed.toFixed(1),
      note: "Of stories, ideas & conversations",
      icon: Clock3,
    },
    {
      label: "Storage used",
      value:
        stats.storage_bytes >= 1024 ** 3
          ? `${(stats.storage_bytes / 1024 ** 3).toFixed(1)} GB`
          : `${(stats.storage_bytes / 1024 ** 2).toFixed(1)} MB`,
      note: "Your source videos & clips",
      icon: HardDrive,
    },
  ];
  return (
    <>
      <div className="page-head dashboard-head" data-reveal>
        <div>
          <div className="welcome-note">
            <span className="studio-indicator" /> YOUR CREATIVE SPACE
          </div>
          <h1>
            Welcome back, {user.name.split(" ")[0]}
            <span className="heading-dot">.</span>
          </h1>
          <p>Let’s make something worth watching.</p>
        </div>
        <Link href="/projects/new" className="button secondary">
          <Plus size={16} aria-hidden="true" /> New Project
        </Link>
      </div>
      <section
        className="creator-hero"
        aria-label="Create your next clip"
        data-reveal
      >
        <div className="creator-hero-copy">
          <span className="hero-kicker">
            <Scissors size={13} aria-hidden="true" /> LESS EDITING. MORE
            CREATING.
          </span>
          <h2>
            Big ideas.
            <br />
            <span>Brilliant little clips.</span>
          </h2>
          <p>
            Your best moments are already in there. Find them, frame them, and
            make every word stand out.
          </p>
          <Link href="/projects/new" className="button hero-upload">
            <Upload size={17} aria-hidden="true" /> Upload a video{" "}
            <ArrowUpRight size={17} aria-hidden="true" />
          </Link>
          <small className="hero-file-note">
            Podcasts, interviews, tutorials. Start with your video.
          </small>
        </div>
        <StudioShowcase />
      </section>
      <section
        className="creator-shortcuts"
        aria-label="Creative tools"
        data-reveal
      >
        {[
          {
            href: "/projects/new",
            icon: Scissors,
            number: "01",
            title: "Find the good parts",
            text: "Turn a long video into your next highlight.",
          },
          {
            href: "/brand-kit",
            icon: Palette,
            number: "02",
            title: "Make your mark",
            text: "Keep every clip recognizably yours.",
          },
        ].map(({ href, icon: Icon, number, title, text }) => (
          <Link href={href} className="creator-shortcut" key={href}>
            <span className="shortcut-icon">
              <Icon size={19} aria-hidden="true" />
            </span>
            <span>
              <small>{number} / CREATE</small>
              <strong>{title}</strong>
              <span>{text}</span>
            </span>
            <ArrowUpRight size={16} aria-hidden="true" />
          </Link>
        ))}
      </section>
      <section
        className="stats studio-stats"
        aria-label="Workspace statistics"
        data-reveal
      >
        {metrics.map(({ label, value, note, icon: Icon }) => (
          <div className="stat" key={label}>
            <div className="stat-top">
              <span>{label}</span>
              <Icon aria-hidden="true" />
            </div>
            <strong>{value}</strong>
            <small>{note}</small>
          </div>
        ))}
      </section>
      <div className="dashboard-columns" data-reveal>
        <div className="dashboard-section">
          <div className="section-head">
            <div>
              <span className="section-kicker">PICK UP WHERE YOU LEFT OFF</span>
              <h2>
                Recent projects{" "}
                <span className="count-label">{projects.length}</span>
              </h2>
            </div>
            <Link className="text-button" href="/projects">
              All projects <ArrowUpRight size={14} />
            </Link>
          </div>
          <section className="panel">
            <ProjectsList
              projects={projects.slice(0, 4)}
              isAdmin={user.is_admin === true}
            />
          </section>
          <div className="section-head">
            <h2>On your editing desk</h2>
            <Link className="text-button" href="/clips">
              All clips <ArrowUpRight size={14} />
            </Link>
          </div>
          <RecentClips items={recent} />
          {stats.clips_created === 0 && (
            <DashboardOnboarding
              userId={user.id}
              hasProject={projects.length > 0}
              hasSource={projects.some((project) => !!project.source_asset_id)}
              projectId={
                projects.find((project) => project.source_asset_id)?.id ??
                projects[0]?.id
              }
            />
          )}
        </div>
        <aside className="dashboard-aside">
          <section className="panel dashboard-sidecard queue-sidecard">
            <h3>
              <Activity size={16} aria-hidden="true" /> In the making{" "}
              <span className="count-label">{stats.processing_jobs}</span>
            </h3>
            {active.length ? (
              active.slice(0, 4).map((project) => (
                <Link
                  className="queue-project"
                  href={`/projects/${project.id}`}
                  key={project.id}
                >
                  <strong>{project.name}</strong>
                  <StatusBadge status={project.status} />
                </Link>
              ))
            ) : (
              <div className="queue-idle">
                <span className="queue-idle-icon">
                  <AudioLines size={25} aria-hidden="true" />
                </span>
                <strong>Ready when you are.</strong>
                <p>
                  Your processing queue is clear.
                  <br />
                  Give your next idea a little screen time.
                </p>
                <Link href="/projects/new" className="text-button">
                  Start a project <ArrowRight size={13} />
                </Link>
              </div>
            )}
          </section>
          <section className="panel dashboard-sidecard studio-note">
            <span className="section-kicker">A LITTLE CREATIVE HEAD START</span>
            <h3>
              Your brand.
              <br />
              On every single clip.
            </h3>
            <p>
              Keep your identity consistent across every clip.
            </p>
            <Link href="/brand-kit" className="quick-link">
              <Palette aria-hidden="true" />
              <span>
                <strong>Brand kit</strong>
                <small>Your colors, logo & identity</small>
              </span>
              <ArrowUpRight aria-hidden="true" />
            </Link>
          </section>
        </aside>
      </div>
    </>
  );
}
