import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { User } from "./api";

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
  if (!response.ok)
    throw new Error("Could not load your workspace. Please try again.");
  return response.json() as Promise<T>;
}
export const getUser = () => serverApi<User>("/me");
