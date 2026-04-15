import { clerkMiddleware } from '@clerk/nextjs/server';
import { NextResponse } from 'next/server';

const hasClerkKeys = Boolean(
  process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY
);

const clerk = clerkMiddleware((auth, req) => {
  const { pathname } = req.nextUrl;

  if (pathname === '/dashboard/certificates') {
    return NextResponse.rewrite(new URL('/dashboard/certificates/', req.url));
  }

  return NextResponse.next();
});

export default async function middleware(req: Request, evt: { waitUntil: (p: Promise<unknown>) => void }) {
  if (!hasClerkKeys) {
    return NextResponse.next();
  }
  return clerk(req as Parameters<typeof clerk>[0], evt as Parameters<typeof clerk>[1]);
}

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
};
