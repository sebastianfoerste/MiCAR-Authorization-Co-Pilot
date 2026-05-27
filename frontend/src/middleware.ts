import { auth } from "../auth";

export const runtime = "nodejs";

export default auth((req) => {
  const isAuthed = !!req.auth;
  const path = req.nextUrl.pathname;
  const isPublic =
    path === "/sign-in" || path.startsWith("/api/auth") || path.startsWith("/_next");
  if (!isAuthed && !isPublic) {
    const url = req.nextUrl.clone();
    url.pathname = "/sign-in";
    return Response.redirect(url);
  }
});

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
