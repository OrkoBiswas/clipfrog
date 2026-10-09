import { ProjectForm } from "@/components/project-form";
export default function NewProject() {
  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">Create clips from a video</p>
          <h1>New project</h1>
          <p>Upload a video and choose your clip options. We’ll guide you through analysis, highlights, and downloads.</p>
        </div>
      </div>
      <ProjectForm />
    </>
  );
}
