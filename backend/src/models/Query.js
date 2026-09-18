import mongoose from "mongoose";
import crypto from "crypto";

/**
 * Query — log of each user search + GQE expansion results.
 *
 * Acts as both a search log and a GQE cache (keyed by queryHash).
 * queryHash = SHA-256(rawQuery.toLowerCase().trim())
 */
const querySchema = new mongoose.Schema(
  {
    rawQuery:       { type: String, required: true },

    /** SHA-256 hash of normalized query — used for GQE cache lookup */
    queryHash: {
      type: String,
      index: true,
    },

    /** All LLM-generated variants (before clustering) */
    expandedVariants: [String],

    /** K-Means selected representative variants (K=3) */
    representativeQueries: [String],

    /** Predicted dominant modality from classifier */
    predictedModality: {
      type: String,
      enum: ["visual", "speech", "ocr", "all"],
      default: "all",
    },

    /** Fixed-weight fusion weights used for this query */
    modalityWeights: {
      visual: { type: Number, default: 0.33 },
      speech: { type: Number, default: 0.33 },
      ocr:    { type: Number, default: 0.34 },
    },

    resultCount:  { type: Number, default: 0 },
    searchedBy:   { type: mongoose.Schema.Types.ObjectId, ref: "User", default: null },

    /** Model used for expansion */
    expansionModel: { type: String, default: "flan-t5-base" },
  },
  { timestamps: true }
);

/** Static helper: compute query hash */
querySchema.statics.computeHash = function (rawQuery) {
  return crypto
    .createHash("sha256")
    .update(rawQuery.toLowerCase().trim())
    .digest("hex");
};

export default mongoose.model("Query", querySchema);

