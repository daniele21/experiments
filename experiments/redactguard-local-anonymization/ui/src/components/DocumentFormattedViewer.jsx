/**
 * DocumentFormattedViewer.jsx
 *
 * Renders document text as rich, formatted HTML elements (tables, headings, paragraphs)
 * while preserving 100% of the interactive PII span objects and redaction toggles.
 * Transforms raw markdown tables from spreadsheets and CSVs into clean, beautiful HTML tables.
 */

import { useMemo } from "react";
import DocumentSpanItem from "./DocumentSpanItem";

/**
 * Splits a line (array of segments) into table cells by splitting on '|' characters.
 */
function splitLineIntoCells(lineSegments) {
  const cells = [];
  let currentCell = [];

  for (let sIdx = 0; sIdx < lineSegments.length; sIdx++) {
    const seg = lineSegments[sIdx];

    if (seg.type === "text") {
      const parts = seg.content.split("|");
      for (let p = 0; p < parts.length; p++) {
        const textChunk = parts[p];
        if (textChunk) {
          currentCell.push({
            ...seg,
            id: `${seg.id}-part-${p}`,
            content: textChunk,
          });
        }
        if (p < parts.length - 1) {
          cells.push(currentCell);
          currentCell = [];
        }
      }
    } else {
      // PII Span segment stays intact
      currentCell.push(seg);
    }
  }

  if (currentCell.length > 0) {
    cells.push(currentCell);
  }

  // Remove empty leading/trailing cells that result from bounding '|' characters
  const trimmed = cells.filter((cell, idx) => {
    if (idx === 0 || idx === cells.length - 1) {
      const str = cell.map((s) => s.content).join("").trim();
      return str !== "";
    }
    return true;
  });

  return trimmed.length > 0 ? trimmed : cells;
}

/**
 * Checks if a line is a markdown table separator line (e.g. |---|---| or |:---|---:|).
 */
function isTableSeparator(lineSegments) {
  const text = lineSegments.map((s) => s.content).join("").trim();
  return /^\s*\|?(\s*:?-{2,}:?\s*\|)+\s*$/.test(text);
}

/**
 * Checks if a line is a table row (starts and ends with '|' or contains multiple '|').
 */
function isTableRow(lineSegments) {
  const text = lineSegments.map((s) => s.content).join("").trim();
  return text.startsWith("|") && text.endsWith("|") && text.length > 2;
}

/**
 * Extracts line text representation.
 */
function getLineText(lineSegments) {
  return lineSegments.map((s) => s.content).join("");
}

export function DocumentFormattedViewer({
  segments = [],
  redactionStyle = "block",
  density = "compact",
  onToggleSpan,
  searchQuery = "",
  modelTitle = null,
}) {
  // 1. Group segments into lines
  const lines = useMemo(() => {
    const result = [];
    let currentLine = [];

    for (let i = 0; i < segments.length; i++) {
      const seg = segments[i];

      if (seg.type === "text") {
        const parts = seg.content.split("\n");
        for (let p = 0; p < parts.length; p++) {
          const part = parts[p];
          if (part.length > 0) {
            currentLine.push({
              ...seg,
              id: `${seg.id}-ln-${p}`,
              content: part,
            });
          }
          if (p < parts.length - 1) {
            result.push(currentLine);
            currentLine = [];
          }
        }
      } else {
        currentLine.push(seg);
      }
    }

    if (currentLine.length > 0) {
      result.push(currentLine);
    }

    return result;
  }, [segments]);

  // 2. Parse lines into structured blocks (Table, Heading, Paragraph, Divider)
  const blocks = useMemo(() => {
    const parsed = [];
    let idx = 0;

    while (idx < lines.length) {
      const line = lines[idx];
      const text = getLineText(line).trim();

      // Skip blank lines
      if (!text) {
        idx++;
        continue;
      }

      // Check for Table Block
      if (isTableRow(line)) {
        const tableRows = [];
        let hasSeparator = false;

        while (idx < lines.length && (isTableRow(lines[idx]) || isTableSeparator(lines[idx]))) {
          if (isTableSeparator(lines[idx])) {
            hasSeparator = true;
          } else {
            tableRows.push(lines[idx]);
          }
          idx++;
        }

        parsed.push({
          type: "table",
          hasHeader: hasSeparator,
          rows: tableRows,
        });
        continue;
      }

      // Check for Headings
      if (text.startsWith("### ")) {
        parsed.push({
          type: "heading3",
          content: line,
        });
        idx++;
        continue;
      }
      if (text.startsWith("## ")) {
        parsed.push({
          type: "heading2",
          content: line,
        });
        idx++;
        continue;
      }
      if (text.startsWith("# ")) {
        parsed.push({
          type: "heading1",
          content: line,
        });
        idx++;
        continue;
      }

      // Check for Horizontal Rule
      if (text === "---" || text === "***" || text === "___") {
        parsed.push({ type: "divider" });
        idx++;
        continue;
      }

      // Group consecutive non-empty lines into a Paragraph
      const paraLines = [];
      while (
        idx < lines.length &&
        getLineText(lines[idx]).trim() !== "" &&
        !isTableRow(lines[idx]) &&
        !getLineText(lines[idx]).trim().startsWith("#") &&
        getLineText(lines[idx]).trim() !== "---"
      ) {
        paraLines.push(lines[idx]);
        idx++;
      }

      parsed.push({
        type: "paragraph",
        lines: paraLines,
      });
    }

    return parsed;
  }, [lines]);

  // Helper to render an array of segments (with search highlighting and spans)
  const renderSegments = (segs, keyPrefix = "seg") => {
    return segs.map((seg, sIdx) => {
      if (seg.type === "span") {
        return (
          <DocumentSpanItem
            key={seg.id || `${keyPrefix}-span-${sIdx}`}
            span={seg}
            style={redactionStyle}
            density={density}
            onToggle={onToggleSpan}
            isToggledByUser={seg.isToggledByUser}
          />
        );
      }

      // Plain text chunk (with search highlight if matching)
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const content = seg.content;
        const lower = content.toLowerCase();
        let start = 0;
        let match = lower.indexOf(q, start);

        if (match !== -1) {
          const parts = [];
          while (match !== -1) {
            if (match > start) {
              parts.push(content.substring(start, match));
            }
            parts.push(
              <mark key={`${keyPrefix}-srch-${sIdx}-${match}`} className="search-match">
                {content.substring(match, match + q.length)}
              </mark>,
            );
            start = match + q.length;
            match = lower.indexOf(q, start);
          }
          if (start < content.length) {
            parts.push(content.substring(start));
          }
          return <span key={`${keyPrefix}-txt-${sIdx}`}>{parts}</span>;
        }
      }

      return <span key={`${keyPrefix}-txt-${sIdx}`}>{seg.content}</span>;
    });
  };

  return (
    <div className="doc-formatted-container">
      {modelTitle && (
        <div className="canvas-header-badge">
          <strong>{modelTitle}</strong>
        </div>
      )}

      <div className="doc-formatted-body">
        {blocks.map((block, bIdx) => {
          // ================= RENDER TABLE =================
          if (block.type === "table") {
            const [headerRow, ...bodyRows] = block.hasHeader
              ? block.rows
              : [[], ...block.rows];

            const headerCells = headerRow ? splitLineIntoCells(headerRow) : [];

            return (
              <div key={bIdx} className="doc-table-wrapper">
                <table className="doc-rendered-table">
                  {block.hasHeader && headerCells.length > 0 && (
                    <thead>
                      <tr>
                        {headerCells.map((cell, cIdx) => (
                          <th key={cIdx} className="doc-th">
                            {renderSegments(cell, `th-${bIdx}-${cIdx}`)}
                          </th>
                        ))}
                      </tr>
                    </thead>
                  )}
                  <tbody>
                    {(block.hasHeader ? bodyRows : block.rows).map((row, rIdx) => {
                      const cells = splitLineIntoCells(row);
                      return (
                        <tr key={rIdx} className="doc-tr">
                          {cells.map((cell, cIdx) => (
                            <td key={cIdx} className="doc-td">
                              {renderSegments(cell, `td-${bIdx}-${rIdx}-${cIdx}`)}
                            </td>
                          ))}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            );
          }

          // ================= RENDER HEADINGS =================
          if (block.type === "heading1") {
            // Strip leading '# '
            const stripped = block.content.map((s, idx) => {
              if (idx === 0 && s.type === "text") {
                return { ...s, content: s.content.replace(/^#\s+/, "") };
              }
              return s;
            });
            return (
              <h2 key={bIdx} className="doc-h1">
                {renderSegments(stripped, `h1-${bIdx}`)}
              </h2>
            );
          }

          if (block.type === "heading2") {
            const stripped = block.content.map((s, idx) => {
              if (idx === 0 && s.type === "text") {
                return { ...s, content: s.content.replace(/^##\s+/, "") };
              }
              return s;
            });
            return (
              <h3 key={bIdx} className="doc-h2">
                {renderSegments(stripped, `h2-${bIdx}`)}
              </h3>
            );
          }

          if (block.type === "heading3") {
            const stripped = block.content.map((s, idx) => {
              if (idx === 0 && s.type === "text") {
                return { ...s, content: s.content.replace(/^###\s+/, "") };
              }
              return s;
            });
            return (
              <h4 key={bIdx} className="doc-h3">
                {renderSegments(stripped, `h3-${bIdx}`)}
              </h4>
            );
          }

          // ================= RENDER DIVIDER =================
          if (block.type === "divider") {
            return <hr key={bIdx} className="doc-rendered-hr" />;
          }

          // ================= RENDER PARAGRAPH =================
          if (block.type === "paragraph") {
            return (
              <p key={bIdx} className="doc-rendered-p">
                {block.lines.map((pLine, lIdx) => (
                  <span key={lIdx} className="doc-p-line">
                    {renderSegments(pLine, `p-${bIdx}-${lIdx}`)}
                    {lIdx < block.lines.length - 1 && " "}
                  </span>
                ))}
              </p>
            );
          }

          return null;
        })}
      </div>
    </div>
  );
}

export default DocumentFormattedViewer;
