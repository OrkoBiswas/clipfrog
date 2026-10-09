import Link from "next/link";
import { ArrowUpRight, Clapperboard } from "lucide-react";
import { ClipsLibrary, type Clip } from "@/components/clips-panel";
import { serverApi } from "@/lib/server";
import type { Project } from "@/lib/api";
export default async function ClipsPage() {
  const projects = await serverApi<Project[]>("/projects");
  const groups = await Promise.all(
    projects.map(async (project) => ({
      project: { id: project.id, name: project.name, status: project.status },
      clips: await serverApi<Clip[]>(`/projects/${project.id}/clips`),
    })),
  );
  const clips = groups.flatMap((group) => group.clips);
  const rendered = clips.filter((clip) => clip.output_asset_id).length;
  return (
    <div className="studio-library-page">
      <div className="page-head studio-library-heading">
        <div>
          <p className="eyebrow">
            <Clapperboard size={14} aria-hidden="true" /> Your content library
          </p>
          <h1>
            Your clips<span>.</span>
          </h1>
          <p>
            Every highlight, one creative home. Preview, refine, and make it
            yours.
          </p>
        </div>
        <Link className="button primary" href="/projects/new">
          Create a project <ArrowUpRight size={17} aria-hidden="true" />
        </Link>
      </div>
      <dl className="studio-library-summary" aria-label="Library overview">
        <div>
          <dt>Total clips</dt>
          <dd>{clips.length}</dd>
        </div>
        <div>
          <dt>Rendered</dt>
          <dd>{rendered}</dd>
        </div>
        <div>
          <dt>Source projects</dt>
          <dd>{groups.filter((group) => group.clips.length).length}</dd>
        </div>
      </dl>
      <ClipsLibrary groups={groups} />
    </div>
  );
}
