import { ProjectForm } from "@/components/project-form";
export default function NewProject() {
  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">From long-form to share-worthy</p>
          <h1>New project</h1>
          <p>Set the direction. We’ll keep everything together.</p>
        </div>
      </div>
      <ProjectForm />
    </>
  );
}
