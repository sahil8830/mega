import mongoose from "mongoose";

/**
 * Segment — one temporal chunk of a video.
 *
 * Created by the ML service during offline indexing (Phase 1).
 * Each video produces N segments depending on duration and chunk size.
 *
 * Embeddings are stored as flat float arrays (CLIP ViT-B/32 = 512-dim).
 * The FAISS indices store only the vector IDs; this collection stores
 * the full metadata + embeddings for reindexing without reprocessing.
 */
const segmentSchema = new mongoose.Schema(
  {
    videoId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Video",
      required: true,
      index: true,
    },
    chunkId: {
      type: Number,
      required: true,
    },
    startTime: {
      type: Number,
      required: true,
      description: "Chunk start time in seconds",
    },
    endTime: {
      type: Number,
      required: true,
      description: "Chunk end time in seconds",
    },
    /** Paths to the sampled representative frames */
    framePaths: [String],

    /** CLIP mean-pooled visual embedding (512 or 768 floats) */
    visualEmbedding: [Number],

    /** Whisper transcript for this chunk */
    transcript: {
      type: String,
      default: "",
    },
    /** CLIP text-encoded speech embedding */
    speechEmbedding: [Number],

    /** PaddleOCR extracted text for this chunk */
    ocrText: {
      type: String,
      default: "",
    },
    /** CLIP text-encoded OCR embedding */
    ocrEmbedding: [Number],

    /** FAISS internal IDs for reverse lookup */
    faissVisualId: { type: Number, default: null },
    faissSpeechId: { type: Number, default: null },
    faissOcrId: { type: Number, default: null },
  },
  { timestamps: true }
);

segmentSchema.index({ videoId: 1, chunkId: 1 });
segmentSchema.index({ startTime: 1, endTime: 1 });

export default mongoose.model("Segment", segmentSchema);
