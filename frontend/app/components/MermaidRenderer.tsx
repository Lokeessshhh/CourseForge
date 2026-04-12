'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import mermaid from 'mermaid';

// Initialize mermaid once with production settings
let isInitialized = false;

function initializeMermaid() {
  if (isInitialized) return;
  
  try {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'default',
      securityLevel: 'loose',
      fontFamily: 'inherit',
      fontSize: 14,
      flowchart: {
        useMaxWidth: true,
        htmlLabels: true,
        curve: 'basis',
        padding: 15,
        nodeSpacing: 30,
        rankSpacing: 50,
      },
      sequence: {
        useMaxWidth: true,
        diagramMarginX: 20,
        diagramMarginY: 20,
        actorMargin: 30,
        width: 150,
        height: 65,
      },
      gantt: {
        useMaxWidth: true,
      },
    });
    isInitialized = true;
  } catch (error) {
    console.error('Failed to initialize mermaid:', error);
  }
}

interface MermaidRendererProps {
  chart: string;
  className?: string;
}

export default function MermaidRenderer({ chart, className = '' }: MermaidRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const renderChart = useCallback(async (chartContent: string) => {
    if (!chartContent.trim()) {
      setError('Empty chart');
      setIsLoading(false);
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      initializeMermaid();

      // Generate a unique ID for this chart
      const id = `mermaid-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

      // Render the chart directly - skip parse() validation which is overly strict
      const { svg: renderedSvg } = await mermaid.render(id, chartContent);
      setSvg(renderedSvg);
    } catch (err) {
      console.error('Mermaid render error:', err);
      // Don't show error to user, just show fallback
      setError('Could not render diagram');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    renderChart(chart);
  }, [chart, renderChart]);

  if (isLoading) {
    return (
      <div className={`mermaid-container ${className}`} style={{ 
        minHeight: '200px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f8f9fa',
        borderRadius: '8px',
        margin: '16px 0',
        border: '1px solid #e9ecef',
      }}>
        <div style={{ 
          display: 'flex', 
          flexDirection: 'column', 
          alignItems: 'center', 
          gap: '12px',
          color: '#6c757d',
          fontSize: '14px',
        }}>
          <div style={{
            width: '32px',
            height: '32px',
            border: '3px solid #e9ecef',
            borderTop: '3px solid #0070f3',
            borderRadius: '50%',
            animation: 'spin 1s linear infinite',
          }} />
          <span>Rendering diagram...</span>
          <style>{`
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      </div>
    );
  }

  if (error || !svg) {
    return (
      <div className={`mermaid-container ${className}`} style={{
        minHeight: '120px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#fff3cd',
        borderRadius: '8px',
        margin: '16px 0',
        border: '1px solid #ffc107',
        padding: '16px',
      }}>
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '8px',
          color: '#856404',
          fontSize: '14px',
        }}>
          <span style={{ fontSize: '20px' }}></span>
          <span>Diagram could not be rendered</span>
          <details style={{ 
            fontSize: '12px', 
            color: '#6c757d', 
            marginTop: '8px',
            maxWidth: '100%',
            overflow: 'hidden',
          }}>
            <summary>View raw diagram code</summary>
            <pre style={{ 
              marginTop: '8px',
              padding: '8px',
              background: '#f8f9fa',
              borderRadius: '4px',
              fontSize: '11px',
              maxHeight: '100px',
              overflow: 'auto',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
            }}>
              {chart}
            </pre>
          </details>
        </div>
      </div>
    );
  }

  return (
    <div 
      className={`mermaid-container ${className}`}
      ref={containerRef}
      style={{
        margin: '20px 0',
        padding: '20px',
        background: '#ffffff',
        borderRadius: '12px',
        border: '1px solid #e2e8f0',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05)',
        overflowX: 'auto',
        contain: 'layout style',
      }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
