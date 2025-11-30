import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Redirect /project/orchestrator/* to /infrastructure/orchestrator/*
  if (pathname.startsWith("/project/orchestrator")) {
    const newPath = pathname.replace("/project/orchestrator", "/infrastructure/orchestrator");
    return NextResponse.redirect(new URL(newPath, request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: "/project/orchestrator/:path*",
};

