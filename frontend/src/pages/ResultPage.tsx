/**
 * ResultPage — Phase 6 implementation target.
 *
 * Features (to build in Phase 6):
 * - HTML5 video player that auto-seeks to `start_time`
 * - Highlight bar showing predicted temporal window on video timeline
 * - Evidence breakdown panel with visual/speech/OCR weight progress bars
 * - Answerability score badge (green = high confidence, red = low)
 * - "No relevant video found" state card when answerability is low
 * - Confidence-gated refinement indicator
 */
export default function ResultPage() {
  return (
    <div style={{ padding: "2rem" }}>
      <h1>Search Result</h1>
      <p style={{ color: "#888" }}>
        🚧 Phase 6 — Video player with auto-seek + evidence breakdown panel. Coming soon.
      </p>
    </div>
  );
}
