import styles from './Marquee.module.css';

export default function Marquee() {
  const text = 'FINE-TUNED QWEN 7B ★ 325 BOOKS VECTORIZED ★ 9-COMPONENT RAG ★ AMD MI300X ROCM ★ HYBRID RETRIEVAL ★ BGE-RERANKER-V2-M3 ★ HYDE + QUERY DECOMPOSITION ★ 4-TIER MEMORY ★';

  return (
    <section className={styles.section}>
      <div className={styles.marquee}>
        <div className={styles.track}>
          <span className={styles.text}>{text}</span>
          <span className={styles.text}>{text}</span>
          <span className={styles.text}>{text}</span>
          <span className={styles.text}>{text}</span>
        </div>
      </div>
    </section>
  );
}
