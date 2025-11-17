/**
 * ANSI Color Parser
 * Converts ANSI escape codes to HTML/React elements with proper styling
 */

interface AnsiSegment {
  text: string;
  color?: string;
  bgColor?: string;
  bold?: boolean;
  dim?: boolean;
  italic?: boolean;
  underline?: boolean;
}

// ANSI color mappings (standard 16 colors)
const ansiColors: Record<number, string> = {
  // Foreground colors
  30: '#000000',  // black
  31: '#ef4444',  // red
  32: '#22c55e',  // green
  33: '#eab308',  // yellow
  34: '#3b82f6',  // blue
  35: '#a855f7',  // magenta
  36: '#06b6d4',  // cyan
  37: '#d1d5db',  // white
  
  // Bright foreground colors
  90: '#6b7280',  // bright black (gray)
  91: '#f87171',  // bright red
  92: '#4ade80',  // bright green
  93: '#fbbf24',  // bright yellow
  94: '#60a5fa',  // bright blue
  95: '#c084fc',  // bright magenta
  96: '#22d3ee',  // bright cyan
  97: '#f3f4f6',  // bright white
};

const ansiBgColors: Record<number, string> = {
  // Background colors
  40: '#000000',  // black
  41: '#ef4444',  // red
  42: '#22c55e',  // green
  43: '#eab308',  // yellow
  44: '#3b82f6',  // blue
  45: '#a855f7',  // magenta
  46: '#06b6d4',  // cyan
  47: '#d1d5db',  // white
  
  // Bright background colors
  100: '#6b7280', // bright black (gray)
  101: '#f87171', // bright red
  102: '#4ade80', // bright green
  103: '#fbbf24', // bright yellow
  104: '#60a5fa', // bright blue
  105: '#c084fc', // bright magenta
  106: '#22d3ee', // bright cyan
  107: '#f3f4f6', // bright white
};

/**
 * Parse ANSI escape codes and convert to styled segments
 */
export function parseAnsi(text: string): AnsiSegment[] {
  const segments: AnsiSegment[] = [];
  
  // Regex to match ANSI escape codes: ESC[ + numbers/semicolons + letter
  const ansiRegex = /\x1b\[([0-9;]*)m/g;
  
  let lastIndex = 0;
  let currentStyle: Partial<AnsiSegment> = {};
  let match;
  
  while ((match = ansiRegex.exec(text)) !== null) {
    // Add text before this escape code
    if (match.index > lastIndex) {
      const textContent = text.substring(lastIndex, match.index);
      if (textContent) {
        segments.push({ text: textContent, ...currentStyle });
      }
    }
    
    // Parse the escape code
    const codes = match[1].split(';').map(Number);
    for (const code of codes) {
      if (code === 0 || !code) {
        // Reset all styles
        currentStyle = {};
      } else if (code === 1) {
        currentStyle.bold = true;
      } else if (code === 2) {
        currentStyle.dim = true;
      } else if (code === 3) {
        currentStyle.italic = true;
      } else if (code === 4) {
        currentStyle.underline = true;
      } else if (code >= 30 && code <= 37) {
        currentStyle.color = ansiColors[code];
      } else if (code >= 40 && code <= 47) {
        currentStyle.bgColor = ansiBgColors[code];
      } else if (code >= 90 && code <= 97) {
        currentStyle.color = ansiColors[code];
      } else if (code >= 100 && code <= 107) {
        currentStyle.bgColor = ansiBgColors[code];
      } else if (code === 39) {
        // Default foreground color
        delete currentStyle.color;
      } else if (code === 49) {
        // Default background color
        delete currentStyle.bgColor;
      }
    }
    
    lastIndex = ansiRegex.lastIndex;
  }
  
  // Add remaining text
  if (lastIndex < text.length) {
    const textContent = text.substring(lastIndex);
    if (textContent) {
      segments.push({ text: textContent, ...currentStyle });
    }
  }
  
  // If no ANSI codes found, return original text as single segment
  if (segments.length === 0 && text) {
    segments.push({ text });
  }
  
  return segments;
}

/**
 * Convert styled segment to inline CSS style object
 */
export function segmentToStyle(segment: AnsiSegment): React.CSSProperties {
  const style: React.CSSProperties = {};
  
  if (segment.color) {
    style.color = segment.color;
  }
  
  if (segment.bgColor) {
    style.backgroundColor = segment.bgColor;
  }
  
  if (segment.bold) {
    style.fontWeight = 'bold';
  }
  
  if (segment.dim) {
    style.opacity = 0.6;
  }
  
  if (segment.italic) {
    style.fontStyle = 'italic';
  }
  
  if (segment.underline) {
    style.textDecoration = 'underline';
  }
  
  return style;
}

/**
 * Strip ANSI codes from text (for plain text fallback)
 */
export function stripAnsi(text: string): string {
  return text.replace(/\x1b\[[0-9;]*m/g, '');
}

