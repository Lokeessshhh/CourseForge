'use client';

import { motion, useInView, useMotionValue, animate } from 'framer-motion';
import { useRef, useEffect, useState } from 'react';
import styles from './Stats.module.css';

const stats = [
  { value: 87.0, suffix: '%', label: 'HumanEval Score' },
  { value: 325, suffix: '', label: 'Books in Knowledge Base' },
  { value: 9, suffix: '', label: 'RAG Components' },
  { value: 200, suffix: 'ms', prefix: '<', label: 'Response Time' },
];

function StatCounter({ value, suffix, prefix }: { value: number; suffix: string; prefix?: string }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });
  const motionValue = useMotionValue(0);
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    if (isInView) {
      const controls = animate(motionValue, value, {
        duration: 1.5,
        ease: 'easeOut',
      });

      const unsubscribe = motionValue.on('change', (latest) => {
        setDisplayValue(Math.round(latest * 10) / 10);
      });

      return () => {
        controls.stop();
        unsubscribe();
      };
    }
  }, [isInView, motionValue, value]);

  return (
    <span ref={ref}>
      {prefix}{displayValue}{suffix}
    </span>
  );
}

export default function Stats() {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section className={styles.section} ref={ref}>
      <div className={styles.container}>
        <div className={styles.label}>── 04 / BY THE NUMBERS ──</div>

        <div className={styles.grid}>
          {stats.map((stat, index) => (
            <motion.div
              key={stat.label}
              className={styles.card}
              initial={{ opacity: 0, y: 30 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.5, delay: index * 0.1 }}
            >
              <div className={styles.value}>
                <StatCounter value={stat.value} suffix={stat.suffix} prefix={stat.prefix} />
              </div>
              <div className={styles.labelText}>{stat.label}</div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
