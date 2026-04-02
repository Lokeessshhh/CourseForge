'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import styles from './WebSearchStatus.module.css';
import { WebSearchState } from '@/app/hooks/api/useChat';

interface Props {
  webSearchState: WebSearchState;
}

export default function WebSearchStatus({ webSearchState }: Props) {
  const { isActive, query, results, success } = webSearchState;
  const [isExpanded, setIsExpanded] = useState(false);

  // Auto-expand when searching or just completed
  const shouldShowFull = isActive || (isExpanded && results.length > 0 && success);

  return (
    <AnimatePresence>
      {(isActive || (results.length > 0 && success)) && (
        <motion.div
          className={styles.container}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2 }}
        >
          {isActive && (
            <div className={styles.searchingState}>
              <div className={styles.searchingContent}>
                <span className={styles.searchingIcon}>🔍</span>
                <span className={styles.searchingText}>SEARCHING WEB</span>
                <div className={styles.searchingDots}>
                  <span className={styles.dot}></span>
                  <span className={styles.dot}></span>
                  <span className={styles.dot}></span>
                </div>
              </div>
              <div className={styles.searchingQuery}>
                <span className={styles.queryLabel}>Query:</span>
                <span className={styles.queryText}>&quot;{query}&quot;</span>
              </div>
            </div>
          )}

          {!isActive && results.length > 0 && success && (
            <div className={`${styles.resultsState} ${shouldShowFull ? styles.expanded : ''}`}>
              <div 
                className={styles.resultsHeader}
                onClick={() => setIsExpanded(!isExpanded)}
              >
                <span className={styles.resultsIcon}>🌐</span>
                <span className={styles.resultsTitle}>WEB SEARCH</span>
                <span className={styles.resultsCount}>{results.length} sources</span>
                <span className={styles.toggleIcon}>{isExpanded ? '▼' : '▲'}</span>
              </div>
              
              <AnimatePresence>
                {shouldShowFull && (
                  <motion.div
                    className={styles.resultsList}
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    {results.map((result, index) => (
                      <a
                        key={index}
                        href={result.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={styles.resultItem}
                      >
                        <div className={styles.resultIndex}>{index + 1}</div>
                        <div className={styles.resultContent}>
                          <div className={styles.resultTitle}>{result.title}</div>
                          <div className={styles.resultSnippet}>{result.snippet}</div>
                          <div className={styles.resultSource}>{result.source || result.url}</div>
                        </div>
                      </a>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
