import Link from "next/link";
import { ArrowLeft, Clock3, Film, Ratio } from "lucide-react";
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
  const [project, kits, highlights] = await Promise.all([
    serverApi<Project>(`/projects/${id}`),
    serverApi<BrandKit[]>("/brand-kits"),
    serverApi<{ items: { id: string }[] }>(`/projects/${id}/highlights`),
  ]);
  return (
    <>
      <Link href="/projects" className="text-button px-back-link">
        <ArrowLeft size={14} aria-hidden="true" /> All projects
      </Link>
      <div className="page-head px-studio-head">
        <div>
          <p className="eyebrow">Project studio</p>
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
      <dl className="px-studio-output" aria-label="Output configuration">
        <div>
          <dt>
            <Film size={14} aria-hidden="true" />
            Up to
          </dt>
          <dd>{project.processing_config.clip_count} {project.processing_config.clip_count === 1 ? "highlight" : "highlights"}</dd>
        </div>
        <div>
          <dt>
            <Clock3 size={14} aria-hidden="true" />
            Target length
          </dt>
          <dd>
            {project.processing_config.duration_min}–
            {project.processing_config.duration_max} seconds
          </dd>
        </div>
        <div>
          <dt>
            <Ratio size={14} aria-hidden="true" />
            Formats
          </dt>
          <dd>{project.processing_config.ratios.join(", ")}</dd>
        </div>
      </dl>
      <ProjectWorkspace
        key={project.id}
        status={project.status}
        hasSource={!!project.source_asset_id}
        highlightCount={highlights.items.length}
        overview={
          <div className="px-studio-overview">
            <div id="source" className="px-project-section" tabIndex={-1}>
              <SourceUpload
                projectId={project.id}
                projectStatus={project.status}
              />
            </div>
            <div id="analysis" className="px-project-section" tabIndex={-1}>
              <AnalysisPanel projectId={project.id} status={project.status} />
            </div>
            <div id="highlights" className="px-project-section" tabIndex={-1}>
              <HighlightsPanel
                projectId={project.id}
                status={project.status}
                ratios={project.processing_config.ratios}
              />
            </div>
          </div>
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
            processingConfig={project.processing_config}
          />
        }
        settings={<ProjectActions project={project} />}
      />
    </>
  );
}
