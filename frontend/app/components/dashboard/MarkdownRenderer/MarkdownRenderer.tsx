'use client';

import { useMemo } from 'react';
import dynamic from 'next/dynamic';
import styles from './MarkdownRenderer.module.css';

// Dynamically import MermaidRenderer to disable SSR
// This prevents "window is not defined" and "Module not found" errors during build
const MermaidRenderer = dynamic(() => import('@/app/components/MermaidRenderer'), {
  ssr: false,
  loading: () => (
    <div style={{ 
      minHeight: '200px', 
      background: '#f3f4f6', 
      borderRadius: '8px', 
      margin: '20px 0',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#6b7280',
      fontSize: '14px'
    }}>
      Loading diagram...
    </div>
  ),
});

interface MarkdownRendererProps {
  content: string;
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const segments = useMemo(() => {
    return parseMarkdownWithMermaid(content);
  }, [content]);

  return (
    <div className={styles.renderer}>
      {segments.map((segment, index) => {
        if (segment.type === 'mermaid') {
          return (
            <MermaidRenderer
              key={`mermaid-${index}`}
              chart={segment.content}
              className={styles.mermaidWrapper}
            />
          );
        }
        return (
          <div
            key={`html-${index}`}
            className={styles.htmlSegment}
            dangerouslySetInnerHTML={{ __html: segment.content }}
          />
        );
      })}
    </div>
  );
}

interface Segment {
  type: 'html' | 'mermaid';
  content: string;
}

function parseMarkdownWithMermaid(text: string): Segment[] {
  const segments: Segment[] = [];
  
  // Split by mermaid code blocks
  const mermaidRegex = /```mermaid\n([\s\S]*?)```/g;
  let lastIndex = 0;
  let match;
  
  while ((match = mermaidRegex.exec(text)) !== null) {
    // Add text before the mermaid block
    if (match.index > lastIndex) {
      const textBefore = text.slice(lastIndex, match.index);
      segments.push({
        type: 'html',
        content: parseMarkdown(textBefore),
      });
    }
    
    // Add the mermaid block
    segments.push({
      type: 'mermaid',
      content: match[1].trim(),
    });
    
    lastIndex = match.index + match[0].length;
  }
  
  // Add remaining text
  if (lastIndex < text.length) {
    segments.push({
      type: 'html',
      content: parseMarkdown(text.slice(lastIndex)),
    });
  }
  
  return segments;
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
