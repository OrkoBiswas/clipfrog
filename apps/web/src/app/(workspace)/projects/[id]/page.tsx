import { serverApi } from "@/lib/server";
import type { Project } from "@/lib/api";
import { ProjectActions } from "@/components/project-actions";
import { SourceUpload } from "@/components/source-upload";
import { AnalysisPanel } from "@/components/analysis-panel";
import { HighlightsPanel } from "@/components/highlights-panel";
import { ClipsPanel } from "@/components/clips-panel";
import { ProjectBrand, type BrandKit } from "@/components/brand-kits";
import { ProjectWorkspace } from "@/components/project-workspace";
import { StatusBadge } from "@/components/ui/primitives";
export default async function ProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const project = await serverApi<Project>(`/projects/${id}`);
  const kits = await serverApi<BrandKit[]>("/brand-kits");
  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Project overview</p>
          <h1>{project.name}</h1>
          <p>
            {project.content_type} ·{" "}
            {project.language === "auto"
              ? "Auto-detect language"
              : project.language}
          </p>
        </div>
        <StatusBadge status={project.status} />
      </div>
      <section className="panel">
        <h2>Output configuration</h2>
        <dl className="meta-grid">
          <div>
            <dt>Requested clips</dt>
            <dd>{project.processing_config.clip_count}</dd>
          </div>
          <div>
            <dt>Duration</dt>
            <dd>
              {project.processing_config.duration_min}–
              {project.processing_config.duration_max} seconds
            </dd>
          </div>
          <div>
            <dt>Aspect ratios</dt>
            <dd>{project.processing_config.ratios.join(", ")}</dd>
          </div>
        </dl>
      </section>
      <ProjectWorkspace
        overview={
          <>
            <SourceUpload
              projectId={project.id}
              projectStatus={project.status}
            />
            <AnalysisPanel projectId={project.id} status={project.status} />
            <HighlightsPanel
              projectId={project.id}
              status={project.status}
              ratios={project.processing_config.ratios}
            />
          </>
        }
        brand={
          <ProjectBrand
            key={JSON.stringify(project.brand_config)}
            projectId={project.id}
            current={project.brand_config}
            kits={kits}
          />
        }
        clips={
          <ClipsPanel
            projectId={project.id}
            status={project.status}
            brand={project.brand_config}
          />
        }
        settings={<ProjectActions project={project} />}
      />
    </>
  );
}
