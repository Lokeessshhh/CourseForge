import type { Metadata } from 'next';
import { ClerkProvider } from '@clerk/nextjs';
import { ErrorBoundary } from '@/app/components/ErrorBoundary';
import { AuthTokenBridge } from '@/app/components/AuthTokenBridge';
import { LoadingProvider } from '@/app/components/LoadingProvider';
import { GenerationProgressProvider } from '@/app/components/GenerationProgressProvider/GenerationProgressProvider';
import './globals.css';

export const metadata: Metadata = {
  title: 'CourseForge - AI Course Generator',
  description: 'Generate personalized coding courses with AI. Fine-tuned Qwen 7B model with full RAG pipeline.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider publishableKey={process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY}>
      <html lang="en">
        <body>
          <ErrorBoundary>
            <AuthTokenBridge />
            <LoadingProvider>
              <GenerationProgressProvider>
                {children}
              </GenerationProgressProvider>
            </LoadingProvider>
          </ErrorBoundary>
        </body>
      </html>
    </ClerkProvider>
  );
}
