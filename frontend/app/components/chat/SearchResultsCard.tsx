'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import styles from './SearchResultsCard.module.css';

interface SearchResult {
  title: string;
  url: string;
  content: string;
  score: number;
  published_date?: string;
  domain?: string;
}

interface Props {
  results?: SearchResult[];
  query?: string;
  isLoading?: boolean;
}

export default function SearchResultsCard({ results, query, isLoading }: Props) {
  const [expanded, setExpanded] = useState(true);

  if (isLoading) {
    return (
      <motion.div
        className={styles.card}
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className={styles.loadingState}>
          <span className={styles.loadingSpinner}>🔍</span>
          <span className={styles.loadingText}>Searching web...</span>
        </div>
      </motion.div>
    );
  }

  if (!results || results.length === 0) {
    return null;
  }

  return (
    <motion.div
      className={styles.card}
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        className={styles.header}
        type="button"
      >
        <div className={styles.headerLeft}>
          <span className={styles.icon}>🔍</span>
          <span className={styles.title}>
            Search Results{query ? ` for "${query}"` : ''}
          </span>
          <span className={styles.count}>{results.length} sources</span>
        </div>
        <span className={styles.expandIcon}>
          {expanded ? '▼' : '▶'}
        </span>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            className={styles.results}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
          >
            {results.map((result, index) => (
              <motion.div
                key={index}
                className={styles.result}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <a
                  href={result.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.resultLink}
                >
                  <span className={styles.resultTitle}>{result.title}</span>
                </a>
                <div className={styles.resultMeta}>
                  <span className={styles.resultDomain}>
                    {result.domain || new URL(result.url).hostname.replace('www.', '')}
                  </span>
                  <span className={styles.resultScore}>
                    {(result.score * 100).toFixed(0)}% match
                  </span>
                </div>
                <p className={styles.resultContent}>{result.content}</p>
                {result.published_date && (
                  <div className={styles.resultDate}>
                    📅 {new Date(result.published_date).toLocaleDateString()}
                  </div>
                )}
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
