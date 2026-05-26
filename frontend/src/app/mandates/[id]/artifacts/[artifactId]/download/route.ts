import { backendFetch } from "@/lib/backend";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string; artifactId: string }> },
) {
  const { artifactId } = await params;
  const response = await backendFetch(`/artifacts/${artifactId}/download`);
  const headers = new Headers();
  const contentType = response.headers.get("content-type");
  const disposition = response.headers.get("content-disposition");
  if (contentType) headers.set("content-type", contentType);
  if (disposition) headers.set("content-disposition", disposition);
  return new Response(response.body, { status: response.status, headers });
}
