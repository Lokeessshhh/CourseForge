import { useEffect, useState, useRef, useCallback } from 'react';

interface Section {
  id: string;
  label: string;
}

export function useActiveSection(sections: Section[]) {
  const [activeSection, setActiveSection] = useState<string>(sections[0]?.id || '');
  const sectionRefs = useRef<Map<string, HTMLElement | null>>(new Map());

  const registerRef = useCallback((id: string) => {
    return (el: HTMLElement | null) => {
      sectionRefs.current.set(id, el);
    };
  }, []);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        });
      },
      {
        threshold: 0.3,
        rootMargin: '-20% 0px -60% 0px',
      }
    );

    sectionRefs.current.forEach((el) => {
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [sections]);

  const scrollToSection = useCallback((id: string) => {
    const el = sectionRefs.current.get(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  return { activeSection, registerRef, scrollToSection };
}
