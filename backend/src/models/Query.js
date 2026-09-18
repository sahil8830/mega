import mongoose from "mongoose";
import crypto from "crypto";

/**
 * Query — cached GQE expansion results, keyed by query hash.
 *
 * Avoids redundant LLM API calls for identical or near-identical queries.
 * queryHash = MD5(rawQuery.toLowerCase().trim())
 */
const querySchema = new mongoose.Schema(
  {
    rawQuery: {
      type: String,
      required: true,
    },
    /**
     * MD5 hash of normalized query for fast lookup.
     * Normalized = lowercase + trimmed.
     */
    queryHash: {
      type: String,
      required: true,
      unique: true,
      index: true,
    },
    /** All LLM-generated variants (before clustering) */
    expandedVariants: [String],
    /** K-Means selected representative variants (K=3) */
    representativeVariants: [String],
    /** Model used for expansion: "flan-t5-base" | "gpt-3.5-turbo" */
    expansionModel: {
      type: String,
      default: "flan-t5-base",
    },
    cachedAt: {
      type: Date,
      default: Date.now,
    },
  },
  { timestamps: true }
);

/**
 * Static helper: compute query hash
 */
querySchema.statics.computeHash = function (rawQuery) {
  return crypto
    .createHash("md5")
    .update(rawQuery.toLowerCase().trim())
    .digest("hex");
};

export default mongoose.model("Query", querySchema);
