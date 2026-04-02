'use client';

import { useMemo } from 'react';
import styles from './MarkdownRenderer.module.css';

interface MarkdownRendererProps {
  content: string;
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const html = useMemo(() => {
    return parseMarkdown(content);
  }, [content]);

  return (
    <div
      className={styles.renderer}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function parseMarkdown(text: string): string {
  let html = text;

  // Escape HTML
  html = html
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Code blocks (must be before inline code)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    return `<pre class="${styles.codeBlock}"><code class="${styles.code}">${code.trim()}</code></pre>`;
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, `<code class="${styles.inlineCode}">$1</code>`);

  // Headers
  html = html.replace(/^### (.+)$/gm, `<h3 class="${styles.h3}">$1</h3>`);
  html = html.replace(/^## (.+)$/gm, `<h2 class="${styles.h2}">$1</h2>`);
  html = html.replace(/^# (.+)$/gm, `<h1 class="${styles.h1}">$1</h1>`);

  // Bold and Italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, `<strong><em>$1</em></strong>`);
  html = html.replace(/\*\*(.+?)\*\*/g, `<strong class="${styles.bold}">$1</strong>`);
  html = html.replace(/\*(.+?)\*/g, `<em>$1</em>`);

  // Blockquotes
  html = html.replace(/^&gt; (.+)$/gm, `<blockquote class="${styles.blockquote}">$1</blockquote>`);

  // Unordered lists
  html = html.replace(/^- (.+)$/gm, `<li class="${styles.listItem}"><span class="${styles.bullet}">■</span>$1</li>`);
  html = html.replace(/(<li[^>]*>[\s\S]*?<\/li>\n?)+/g, '<ul class="$styles.list}">$&</ul>');

  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, `<li class="${styles.listItem}"><span class="${styles.number}">$&</span></li>`);

  // Links
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, `<a href="$2" class="${styles.link}">$1</a>`);

  // Paragraphs
  html = html.split('\n\n').map(para => {
    if (para.startsWith('<h') || para.startsWith('<ul') || para.startsWith('<pre') || para.startsWith('<blockquote')) {
      return para;
    }
    return `<p class="${styles.paragraph}">${para}</p>`;
  }).join('\n');

  // Line breaks
  html = html.replace(/\n/g, '<br>');

  return html;
}
