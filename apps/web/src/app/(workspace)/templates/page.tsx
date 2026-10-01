import { TemplatesWorkspace } from "@/components/templates-workspace";
export default function TemplatesPage() {
  return (
    <>
      <div className="page-head">
        <div>
          <p className="eyebrow">A signature in every sentence</p>
          <h1>Caption templates</h1>
          <p>
            Find your style, fine-tune the details, and save it for your next
            video.
          </p>
        </div>
      </div>
      <TemplatesWorkspace />
    </>
  );
}
