/**
 * DocumentTextViewer.jsx
 *
 * Comprehensive interactive document viewer with clear UX/UI Information Hierarchy:
 * - Level 1: Document Audit Header (Filename, Model, Safety Verdict & Scorecard)
 * - Level 2: Primary Control Deck (View Mode, Layout, Badge Density, Tools)
 * - Level 3: Secondary Category Filters Drawer (Collapsible to keep deck clean)
 * - Level 4: Document Canvas (Structured Tables or Code Lines with subtle badges)
 * - Level 5: Footer Status Bar (Document Length, Protected Spans, Leaks, User Overrides)
 */

import { useMemo, useState, useCallback, useRef, useEffect } from "react";
import { documentViewerConfig } from "../config/documentViewerConfig";
import {
  buildDocumentSegments,
  generateExportText,
  getPiiTypeSummary,
} from "../utils/textRedactor";
import DocumentTextToolbar from "./DocumentTextToolbar";
import DocumentCategoryFilters from "./DocumentCategoryFilters";
import DocumentSpanItem from "./DocumentSpanItem";
import DocumentFormattedViewer from "./DocumentFormattedViewer";

export function DocumentTextViewer({
  filename,
  documentData,
  modelsList = [],
  profile = "generic",
  fileMetrics = null,
  initialModel = null,
}) {
  const rawText = documentData?.text || "";
  const goldSpans = useMemo(() => documentData?.gold || [], [documentData]);
  const modelsData = useMemo(() => documentData?.models || {}, [documentData]);

  // Determine initial model selection
  const defaultModel = useMemo(() => {
    if (initialModel && (modelsData[initialModel] || initialModel === "__gold__")) {
      return initialModel;
    }
    const available = modelsList.filter((m) => !!modelsData[m]);
    return available[0] || (modelsList[0] ?? "__gold__");
  }, [initialModel, modelsList, modelsData]);

  const [selectedModel, setSelectedModel] = useState(defaultModel);
  const [viewMode, setViewMode] = useState(documentViewerConfig.defaults.viewMode);
  const [renderStyle, setRenderStyle] = useState("formatted"); // "formatted" | "raw"
  const [redactionStyle, setRedactionStyle] = useState(
    documentViewerConfig.defaults.redactionStyle,
  );
  const [badgeDensity, setBadgeDensity] = useState(
    documentViewerConfig.defaults.badgeDensity,
  );
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [toggledSpans, setToggledSpans] = useState(new Set());
  const [disabledTypes, setDisabledTypes] = useState(new Set());
  const [searchQuery, setSearchQuery] = useState("");
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [isSplitView, setIsSplitView] = useState(false);
  const [splitModel, setSplitModel] = useState(
    modelsList.find((m) => m !== defaultModel) || "__gold__",
  );

  const containerRef = useRef(null);

  // Close full screen on Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && isFullScreen) {
        setIsFullScreen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isFullScreen]);

  // Reset individual toggles when switching models
  const handleSelectModel = useCallback((model) => {
    setSelectedModel(model);
    setToggledSpans(new Set());
  }, []);

  // Compute active spans for a given model
  const getSpansForModel = useCallback(
    (modelName) => {
      if (!rawText) return [];

      if (modelName === "__gold__") {
        return goldSpans.map((g, idx) => ({
          ...g,
          id: `gold-${g.start}-${g.end}-${g.pii_type}-${idx}`,
          status: "gold",
        }));
      }

      const m = modelsData[modelName];
      if (!m) return [];

      const missed = m.missed || [];
      const overRedacted = m.overRedacted || [];
      const redactions = m.redactions || [];

      // Gold lookup for ground truth comparison
      const goldExact = new Set(goldSpans.map((g) => `${g.start}:${g.end}`));
      const fpExact = new Set(overRedacted.map((fp) => `${fp.start}:${fp.end}`));

      const allModelSpans = [];

      // 1. Spans recognized and redacted by the model
      for (let i = 0; i < redactions.length; i++) {
        const r = redactions[i];
        const isExactGold = goldExact.has(`${r.start}:${r.end}`);
        const overlapsGold =
          !isExactGold &&
          goldSpans.some((g) => Math.max(g.start, r.start) < Math.min(g.end, r.end));
        const isFp =
          fpExact.has(`${r.start}:${r.end}`) || (!isExactGold && !overlapsGold);

        const status = isFp ? "fp" : "tp";

        allModelSpans.push({
          ...r,
          id: `mod-${modelName}-${r.start}-${r.end}-${r.pii_type}-${i}`,
          status,
          modelName,
        });
      }

      // 2. Missed spans (False Negatives - LEAKS!)
      // These gold PIIs were NOT recognized or redacted by the model: they leaked!
      let effectiveMissed = missed;
      if (
        effectiveMissed.length === 0 &&
        goldSpans.length > 0 &&
        redactions.length < goldSpans.length
      ) {
        const redExact = new Set(redactions.map((r) => `${r.start}:${r.end}`));
        effectiveMissed = goldSpans.filter((g) => !redExact.has(`${g.start}:${g.end}`));
      }

      for (let i = 0; i < effectiveMissed.length; i++) {
        const fn = effectiveMissed[i];
        allModelSpans.push({
          ...fn,
          id: `leak-${modelName}-${fn.start}-${fn.end}-${fn.pii_type}-${i}`,
          status: "fn",
          modelName,
        });
      }

      return allModelSpans;
    },
    [rawText, goldSpans, modelsData],
  );

  const activeSpans = useMemo(
    () => getSpansForModel(selectedModel),
    [getSpansForModel, selectedModel],
  );

  const splitSpans = useMemo(
    () => (isSplitView ? getSpansForModel(splitModel) : []),
    [getSpansForModel, isSplitView, splitModel],
  );

  // Summary of PII types in current document
  const piiTypesSummary = useMemo(() => {
    const combined = [...goldSpans, ...activeSpans];
    return getPiiTypeSummary(combined);
  }, [goldSpans, activeSpans]);

  // Toggle single span redaction state ("togliere e mettere")
  const handleToggleSpan = useCallback((spanId) => {
    setToggledSpans((prev) => {
      const next = new Set(prev);
      if (next.has(spanId)) {
        next.delete(spanId);
      } else {
        next.add(spanId);
      }
      return next;
    });
  }, []);

  // Category level toggles
  const handleToggleType = useCallback((piiType) => {
    setDisabledTypes((prev) => {
      const next = new Set(prev);
      if (next.has(piiType)) {
        next.delete(piiType);
      } else {
        next.add(piiType);
      }
      return next;
    });
  }, []);

  const handleRedactAll = useCallback(() => {
    setDisabledTypes(new Set());
    setToggledSpans(new Set());
    setViewMode("redacted");
  }, []);

  const handleRevealAll = useCallback(() => {
    setViewMode("revealed");
  }, []);

  const handleResetToggles = useCallback(() => {
    setToggledSpans(new Set());
    setDisabledTypes(new Set());
    setViewMode(documentViewerConfig.defaults.viewMode);
  }, []);

  // Copy helpers
  const handleCopyRedacted = useCallback(async () => {
    const text = generateExportText(
      rawText,
      activeSpans,
      { toggledSpans, disabledTypes, viewMode: "redacted" },
      redactionStyle,
    );
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Fallback
    }
  }, [rawText, activeSpans, toggledSpans, disabledTypes, redactionStyle]);

  const handleCopyOriginal = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(rawText);
    } catch {
      // Fallback
    }
  }, [rawText]);

  // Document sliced segments for main panel
  const mainSegments = useMemo(() => {
    return buildDocumentSegments(rawText, activeSpans, {
      toggledSpans,
      disabledTypes,
      viewMode,
      searchQuery,
    });
  }, [rawText, activeSpans, toggledSpans, disabledTypes, viewMode, searchQuery]);

  // Segments for split panel
  const splitSegments = useMemo(() => {
    if (!isSplitView) return [];
    return buildDocumentSegments(rawText, splitSpans, {
      toggledSpans: new Set(),
      disabledTypes,
      viewMode,
      searchQuery,
    });
  }, [isSplitView, rawText, splitSpans, disabledTypes, viewMode, searchQuery]);

  // Metrics summary for active model
  const activeModelMetrics = useMemo(() => {
    if (selectedModel === "__gold__") return null;
    const m = modelsData[selectedModel];
    if (!m) return null;
    return {
      ...m,
      pii_recall: m.pii_recall ?? m.recall ?? null,
      leakage_rate: m.leakage_rate ?? m.leakage ?? null,
    };
  }, [selectedModel, modelsData]);

  // Redaction statistics
  const redactionStats = useMemo(() => {
    const spanSegments = mainSegments.filter((s) => s.type === "span");
    const totalSpans = spanSegments.length;
    const redactedCount = spanSegments.filter((s) => s.isRedacted).length;
    const revealedCount = totalSpans - redactedCount;
    const leakCount = spanSegments.filter((s) => s.status === "fn").length;
    return { totalSpans, redactedCount, revealedCount, leakCount };
  }, [mainSegments]);

  // Render document content (Formatted tables/headings or raw line-numbered canvas)
  const renderDocumentContent = (segments, modelTitle) => {
    if (!rawText) {
      return (
        <div className="doc-empty-canvas">
          <span>📄 Testo del documento non disponibile per questo file.</span>
        </div>
      );
    }

    // Modalità Formattata: Tabelle HTML, titoli tipografici e paragrafi editoriali
    if (renderStyle === "formatted") {
      return (
        <DocumentFormattedViewer
          segments={segments}
          redactionStyle={redactionStyle}
          density={badgeDensity}
          onToggleSpan={handleToggleSpan}
          searchQuery={searchQuery}
          modelTitle={modelTitle}
        />
      );
    }

    // Modalità Grezza / Codice: visualizzazione riga per riga con numerazione
    const lines = [];
    let currentLine = [];

    for (let i = 0; i < segments.length; i++) {
      const seg = segments[i];

      if (seg.type === "text") {
        const textParts = seg.content.split("\n");
        for (let pIdx = 0; pIdx < textParts.length; pIdx++) {
          const part = textParts[pIdx];

          if (part.length > 0) {
            if (searchQuery.trim()) {
              const q = searchQuery.toLowerCase();
              const lower = part.toLowerCase();
              let startIdx = 0;
              let matchIdx = lower.indexOf(q, startIdx);

              if (matchIdx !== -1) {
                const subParts = [];
                while (matchIdx !== -1) {
                  if (matchIdx > startIdx) {
                    subParts.push(part.substring(startIdx, matchIdx));
                  }
                  subParts.push(
                    <mark key={`search-${i}-${matchIdx}`} className="search-match">
                      {part.substring(matchIdx, matchIdx + q.length)}
                    </mark>,
                  );
                  startIdx = matchIdx + q.length;
                  matchIdx = lower.indexOf(q, startIdx);
                }
                if (startIdx < part.length) {
                  subParts.push(part.substring(startIdx));
                }
                currentLine.push(<span key={`text-${i}-${pIdx}`}>{subParts}</span>);
              } else {
                currentLine.push(<span key={`text-${i}-${pIdx}`}>{part}</span>);
              }
            } else {
              currentLine.push(<span key={`text-${i}-${pIdx}`}>{part}</span>);
            }
          }

          if (pIdx < textParts.length - 1) {
            lines.push(currentLine);
            currentLine = [];
          }
        }
      } else {
        // PII Span segment
        currentLine.push(
          <DocumentSpanItem
            key={seg.id}
            span={seg}
            style={redactionStyle}
            density={badgeDensity}
            onToggle={handleToggleSpan}
            isToggledByUser={seg.isToggledByUser}
          />,
        );
      }
    }

    if (currentLine.length > 0) {
      lines.push(currentLine);
    }

    return (
      <div className="doc-code-canvas">
        {modelTitle && (
          <div className="canvas-header-badge">
            <strong>{modelTitle}</strong>
          </div>
        )}
        <div className="doc-lines-list">
          {lines.map((lineContent, lineIdx) => (
            <div key={lineIdx} className="doc-line-row">
              <span className="doc-line-number">{lineIdx + 1}</span>
              <span className="doc-line-content">
                {lineContent.length > 0 ? lineContent : "\u00A0"}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div
      ref={containerRef}
      className={`doc-text-viewer-container ${isFullScreen ? "viewer--fullscreen" : ""}`}
    >
      {/* BARRA UNICA MINIMAL: Modello, Status Leak, Modalità Testo & Strumenti */}
      <DocumentTextToolbar
        models={modelsList}
        selectedModel={selectedModel}
        onSelectModel={handleSelectModel}
        activeModelMetrics={activeModelMetrics}
        viewMode={viewMode}
        onChangeViewMode={setViewMode}
        renderStyle={renderStyle}
        onChangeRenderStyle={setRenderStyle}
        isDrawerOpen={isDrawerOpen}
        onToggleDrawer={() => setIsDrawerOpen((prev) => !prev)}
        disabledTypesCount={disabledTypes.size}
        onCopyRedacted={handleCopyRedacted}
        onCopyOriginal={handleCopyOriginal}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        isFullScreen={isFullScreen}
        onToggleFullScreen={() => setIsFullScreen((prev) => !prev)}
        isSplitView={isSplitView}
        onToggleSplitView={() => setIsSplitView((prev) => !prev)}
        splitModel={splitModel}
        onSelectSplitModel={setSplitModel}
      />

      {/* LIVELLO 3: CASSETTO SECONDARIO FILTRI CATEGORIE & OPZIONI (COLLAPSIBILE) */}
      {isDrawerOpen && (
        <DocumentCategoryFilters
          piiTypesSummary={piiTypesSummary}
          disabledTypes={disabledTypes}
          onToggleType={handleToggleType}
          onRedactAll={handleRedactAll}
          onRevealAll={handleRevealAll}
          onResetToggles={handleResetToggles}
          hasUserToggles={toggledSpans.size > 0 || disabledTypes.size > 0}
          redactionStyle={redactionStyle}
          onChangeRedactionStyle={setRedactionStyle}
          badgeDensity={badgeDensity}
          onChangeBadgeDensity={setBadgeDensity}
        />
      )}

      {/* LIVELLO 4: AREA CANVAS DOCUMENTO (SINGOLA O SPLIT SIDE-BY-SIDE) */}
      <div className={`doc-viewer-body ${isSplitView ? "doc-viewer-body--split" : ""}`}>
        {/* Pannello Primario */}
        <div className="doc-canvas-panel">
          {renderDocumentContent(
            mainSegments,
            isSplitView
              ? selectedModel === "__gold__"
                ? "🎯 Ground Truth"
                : `🤖 ${selectedModel}`
              : null,
          )}
        </div>

        {/* Pannello Split Secondario */}
        {isSplitView && (
          <div className="doc-canvas-panel doc-canvas-panel--split">
            {renderDocumentContent(
              splitSegments,
              splitModel === "__gold__" ? "🎯 Ground Truth" : `🤖 ${splitModel}`,
            )}
          </div>
        )}
      </div>

      {/* LIVELLO 5: STATISTICHE DOCUMENTO A PIÈ DI PAGINA */}
      <footer className="doc-viewer-footer">
        <div className="footer-stat">
          <span className="dot" />
          Caratteri documento: <strong>{rawText.length.toLocaleString()}</strong>
        </div>
        <div className="footer-stat">
          <span className="dot dot--accent" />
          PII Nel Documento: <strong>{redactionStats.totalSpans}</strong>
        </div>
        <div className="footer-stat">
          <span className="dot dot--redacted" />
          Attualmente oscurati: <strong>{redactionStats.redactedCount}</strong>
        </div>
        <div className="footer-stat">
          <span className="dot dot--revealed" />
          In chiaro: <strong>{redactionStats.revealedCount}</strong>
        </div>
        {redactionStats.leakCount > 0 && (
          <div className="footer-stat footer-stat--leak">
            <span className="dot dot--leak" />
            ⚠️ Leak sfuggiti: <strong>{redactionStats.leakCount}</strong>
          </div>
        )}
        {toggledSpans.size > 0 && (
          <div className="footer-stat footer-stat--user">
            ✏️ Modifiche manuali utente: <strong>{toggledSpans.size}</strong>
          </div>
        )}
      </footer>
    </div>
  );
}

export default DocumentTextViewer;
