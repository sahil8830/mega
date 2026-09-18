/**
 * UploadPage — Phase 6 implementation target.
 *
 * Features (to build in Phase 6):
 * - Drag-and-drop video upload with multer multipart POST to /api/videos/upload
 * - Real-time indexing status tracker via polling GET /api/videos/:id/status
 * - Progress bar and status badges (queued → indexing → indexed)
 */
export default function UploadPage() {
  return (
    <div style={{ padding: "2rem" }}>
      <h1>Upload Video</h1>
      <p style={{ color: "#888" }}>
        🚧 Phase 6 — Drag-and-drop upload with real-time indexing status. Coming soon.
      </p>
    </div>
  );
}
