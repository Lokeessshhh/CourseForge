'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';

export default function CodingTestRedirect() {
  const params = useParams();
  const router = useRouter();
  const courseId = params.id as string;
  const week = params.w as string;

  useEffect(() => {
    // Redirect to coding test 1 by default
    router.replace(`/dashboard/courses/${courseId}/week/${week}/coding-test/1`);
  }, [courseId, week, router]);

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
      <p>Redirecting to Coding Test 1...</p>
    </div>
  );
}
