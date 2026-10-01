import Link from "next/link";
import {
  Activity,
  ArrowRight,
  AudioLines,
  Captions,
  Clock3,
  Film,
  Folder,
  HardDrive,
  LayoutTemplate,
  Palette,
  Plus,
  Scissors,
  Sparkles,
  Upload,
} from "lucide-react";
import { getUser, serverApi } from "@/lib/server";
import type { Project, Stats } from "@/lib/api";
import { ProjectsList } from "@/components/projects-list";
import { StatusBadge } from "@/components/ui/primitives";
import {
  DashboardOnboarding,
  RecentClips,
} from "@/components/dashboard-extras";
import type { Clip } from "@/components/clips-panel";

export default async function Dashboard() {
  const [user, projects, stats] = await Promise.all([
    getUser(),
    serverApi<Project[]>("/projects"),
    serverApi<Stats>("/dashboard"),
  ]);
  const groups = await Promise.all(
    projects
      .slice(0, 4)
      .map(async (project) => ({
        project,
        clips: await serverApi<Clip[]>(`/projects/${project.id}/clips`),
      })),
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
      label: "Processing minutes",
      value: stats.minutes_processed.toFixed(1),
      note: "Source video processed",
      icon: Clock3,
    },
    {
      label: "Clips generated",
      value: stats.clips_created,
      note: "Moments ready to make your own",
      icon: Film,
    },
    {
      label: "Storage used",
      value:
        stats.storage_bytes >= 1024 ** 3
          ? `${(stats.storage_bytes / 1024 ** 3).toFixed(1)} GB`
          : `${(stats.storage_bytes / 1024 ** 2).toFixed(1)} MB`,
      note: "Source videos and rendered clips",
      icon: HardDrive,
    },
    {
      label: "Projects",
      value: stats.projects,
      note: "Your creative workspace",
      icon: Folder,
    },
  ];
  return (
    <>
      <div className="page-head dashboard-head">
        <div>
          <div className="welcome-note">
            <Sparkles size={13} aria-hidden="true" /> Welcome back,{" "}
            {user.name.split(" ")[0]}
          </div>
          <h1>Your workspace</h1>
          <p>A little less editing. A lot more creating.</p>
        </div>
        <Link href="/projects/new" className="button">
          <Plus size={16} aria-hidden="true" />
          New Project
        </Link>
      </div>
      <section className="dashboard-hero">
        <div className="dashboard-hero-copy">
          <p className="eyebrow">
            <Sparkles size={12} aria-hidden="true" />
            YOUR NEXT GREAT CLIP STARTS HERE
          </p>
          <h2>
            Long videos.
            <br />
            Standout moments.
          </h2>
          <p>
            Find the best parts of your podcast, interview, or tutorial. Turn
            them into beautifully framed, captioned clips.
          </p>
          <div className="hero-action-row">
            <Link href="/projects/new" className="button">
              <Upload size={15} aria-hidden="true" />
              Upload a video
              <ArrowRight size={14} aria-hidden="true" />
            </Link>
            <small>MP4, MOV, MKV & more</small>
          </div>
        </div>
        <div className="clip-art" aria-hidden="true">
          <div className="art-frame">
            <AudioLines size={27} />
            <span>FIND THE STORY</span>
            <i />
            <i />
          </div>
          <div className="art-frame">
            <Scissors size={31} />
            <span>MAKE THE CUT</span>
            <i />
            <i />
          </div>
          <div className="art-frame">
            <Captions size={27} />
            <span>OWN THE MOMENT</span>
            <i />
            <i />
          </div>
          <span className="art-label">ONE VIDEO. MORE POSSIBILITIES.</span>
        </div>
      </section>
      <section className="stats" aria-label="Workspace statistics">
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
      <div className="dashboard-columns">
        <div className="dashboard-section">
          <div className="section-head">
            <h2>
              Recent projects{" "}
              <span className="count-label">{projects.length}</span>
            </h2>
            <Link className="text-button" href="/projects">
              View all projects <ArrowRight size={13} />
            </Link>
          </div>
          <section className="panel">
            <ProjectsList
              projects={projects.slice(0, 4)}
              isAdmin={user.is_admin === true}
            />
          </section>
          <div className="section-head">
            <h2>Continue editing</h2>
            <Link className="text-button" href="/clips">
              View all clips <ArrowRight size={13} />
            </Link>
          </div>
          <RecentClips items={recent} />
          {stats.clips_created === 0 && (
            <DashboardOnboarding
              userId={user.id}
              hasProject={projects.length > 0}
              hasSource={projects.some((project) => !!project.source_asset_id)}
            />
          )}
        </div>
        <aside className="dashboard-aside">
          <section className="panel dashboard-sidecard">
            <h3>
              <Activity size={15} aria-hidden="true" />
              Processing queue{" "}
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
                <AudioLines size={26} aria-hidden="true" />
                <strong>Room for your next idea</strong>
                <p>
                  No projects processing right now.
                  <br />
                  Your next video is a good place to start.
                </p>
              </div>
            )}
          </section>
          <section className="panel dashboard-sidecard">
            <h3>Your creative toolkit</h3>
            <Link href="/templates" className="quick-link">
              <LayoutTemplate aria-hidden="true" />
              <span>
                <strong>Find your caption style</strong>
                <small>Explore the template library</small>
              </span>
              <ArrowRight aria-hidden="true" />
            </Link>
            <Link href="/brand-kit" className="quick-link">
              <Palette aria-hidden="true" />
              <span>
                <strong>Make it recognizably yours</strong>
                <small>Set up your brand kit</small>
              </span>
              <ArrowRight aria-hidden="true" />
            </Link>
            <Link href="/usage" className="quick-link">
              <Clock3 aria-hidden="true" />
              <span>
                <strong>Keep track of your usage</strong>
                <small>Minutes, renders, and storage</small>
              </span>
              <ArrowRight aria-hidden="true" />
            </Link>
          </section>
        </aside>
      </div>
    </>
  );
}
