import Link from "next/link";
import { serverApi } from "@/lib/server";
import type { Project } from "@/lib/api";
export default async function ClipsPage() {
  const projects = await serverApi<Project[]>("/projects");
  const groups = await Promise.all(
    projects.map(async (project) => ({
      project,
      clips: await serverApi<
        { id: string; title: string; aspect_ratio: string; status: string }[]
      >(`/projects/${project.id}/clips`),
    })),
  );
  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Your media library</p>
          <h1>Clips</h1>
          <p>Open a project to preview, edit and download its clips.</p>
        </div>
      </div>
      <section className="panel">
        {!groups.some((g) => g.clips.length) && (
          <p>No clips yet. Upload a source and render your first moment.</p>
        )}
        {groups
          .filter((g) => g.clips.length)
          .map(({ project, clips }) => (
            <div key={project.id}>
              <h2>
                <Link href={`/projects/${project.id}`}>{project.name}</Link>
              </h2>
              {clips.map((clip) => (
                <p key={clip.id}>
                  <Link href={`/projects/${project.id}`}>{clip.title}</Link> ·{" "}
                  {clip.aspect_ratio} · {clip.status}
                </p>
              ))}
            </div>
          ))}
      </section>
    </>
  );
}
