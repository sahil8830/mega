import mongoose from "mongoose";

/**
 * Video — top-level document created on upload.
 *
 * Lifecycle:
 *   upload → status: "queued"
 *   worker picks up job → status: "indexing"
 *   ML service completes → status: "indexed"
 *   error → status: "failed"
 */
const videoSchema = new mongoose.Schema(
  {
    title: {
      type: String,
      required: true,
      trim: true,
    },
    filename: {
      type: String,
      required: true,
    },
    storagePath: {
      type: String,
      required: true,
    },
    mimeType: {
      type: String,
      default: "video/mp4",
    },
    sizeBytes: {
      type: Number,
      default: 0,
    },
    /** Video duration in seconds — set after ffprobe in Phase 1 */
    duration: {
      type: Number,
      default: null,
    },
    status: {
      type: String,
      enum: ["queued", "indexing", "indexed", "failed"],
      default: "queued",
    },
    errorMessage: {
      type: String,
      default: null,
    },
    /** BullMQ job ID for status tracking */
    jobId: {
      type: String,
      default: null,
    },
    uploadedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      default: null,
    },
  },
  { timestamps: true }
);

// Index for status filtering
videoSchema.index({ status: 1 });
videoSchema.index({ createdAt: -1 });

export default mongoose.model("Video", videoSchema);
