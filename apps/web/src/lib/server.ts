import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { User } from "./api";

export class ServerApiError extends Error {
  constructor(
    readonly status: number,
    readonly path: string,
  ) {
    super(`API request failed with status ${status}: ${path}`);
    this.name = "ServerApiError";
  }
}

export async function serverApi<T>(path: string): Promise<T> {
  const jar = await cookies();
  const response = await fetch(
    `${process.env.API_INTERNAL_URL ?? "http://localhost:8000"}/api/v1${path}`,
    {
      headers: { Cookie: jar.toString() },
      cache: "no-store",
    },
  );
  if (response.status === 401) redirect("/login");
  if (!response.ok) throw new ServerApiError(response.status, path);
  return response.json() as Promise<T>;
}
export const getUser = () => serverApi<User>("/me");
