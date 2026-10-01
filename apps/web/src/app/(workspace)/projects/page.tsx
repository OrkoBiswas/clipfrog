import Link from "next/link";
import { getUser, serverApi } from "@/lib/server";
import type { Project } from "@/lib/api";
import { ProjectsList } from "@/components/projects-list";
export default async function Projects() {
  const [user, projects] = await Promise.all([
    getUser(),
    serverApi<Project[]>("/projects"),
  ]);
  return (
    <>
      <div className="page-head">
        <div>
          <h1>Projects</h1>
          <p>Your source videos and the stories inside them.</p>
        </div>
        <Link className="button" href="/projects/new">
          + New Project
        </Link>
      </div>
      <section className="panel">
        <ProjectsList projects={projects} isAdmin={user.is_admin === true} />
      </section>
    </>
  );
}
