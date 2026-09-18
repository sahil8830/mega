import mongoose from "mongoose";

/**
 * Result — search result returned by the ML service for a given query.
 *
 * Stores the full evidence breakdown for explainability and
 * can be used to log user interactions for future model training.
 */
const evidenceSchema = new mongoose.Schema(
  {
    visualWeight: { type: Number, default: 0 },
    speechWeight: { type: Number, default: 0 },
    ocrWeight: { type: Number, default: 0 },
    visualSimilarity: { type: Number, default: 0 },
    speechSimilarity: { type: Number, default: 0 },
    ocrSimilarity: { type: Number, default: 0 },
  },
  { _id: false }
);

const resultSchema = new mongoose.Schema(
  {
    /** The user's original raw query */
    rawQuery: {
      type: String,
      required: true,
    },
    queryId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Query",
      default: null,
    },
    videoId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Video",
      required: true,
    },
    segmentId: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "Segment",
      default: null,
    },

    /** Predicted temporal window */
    startTime: { type: Number, required: true },
    endTime: { type: Number, required: true },

    /** Answerability gate output [0.0, 1.0] */
    answerabilityScore: { type: Number, default: 0 },

    /** Localization confidence [0.0, 1.0] */
    localizationConfidence: { type: Number, default: 0 },

    /** Whether the expensive refinement pass was triggered */
    refinementTriggered: { type: Boolean, default: false },

    /** Per-modality weights and similarities for explainability */
    evidence: evidenceSchema,

    /** User who made the search (null for anonymous) */
    searchedBy: {
      type: mongoose.Schema.Types.ObjectId,
      ref: "User",
      default: null,
    },

    /** Rank within the result list (1 = top result) */
    rank: { type: Number, default: 1 },
  },
  { timestamps: true }
);

resultSchema.index({ videoId: 1 });
resultSchema.index({ rawQuery: "text" });
resultSchema.index({ createdAt: -1 });

export default mongoose.model("Result", resultSchema);
