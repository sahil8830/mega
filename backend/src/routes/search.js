import express from "express";
import axios   from "axios";
import http    from "http";
import Query   from "../models/Query.js";
import Result  from "../models/Result.js";
import Video   from "../models/Video.js";
import { protect } from "../middleware/auth.js";
import {
  getGqeCache, setGqeCache,
  getSearchCache, setSearchCache,
} from "../utils/searchCache.js";

const router = express.Router();
const ML_SERVICE_URL = process.env.ML_SERVICE_URL || "http://localhost:8001";

// Keep-alive agent — reuses TCP connections to ML service (~10-40ms saved/request)
const mlAgent = new http.Agent({ keepAlive: true, maxSockets: 10 });
const mlAxios = axios.create({
  baseURL:  ML_SERVICE_URL,
  httpAgent: mlAgent,
  timeout:  120_000,  // 2 min max for slow GQE/indexing
});


/**
 * POST /api/search
 * Body: { query: string, topK?: number, useGqe?: boolean }
 *
 * Pipeline with Redis short-circuits:
 *  0. Redis search cache HIT  → return in <5 ms  (skip everything)
 *  1. Redis GQE cache HIT     → skip flan-t5 (saves 5–30 s)
 *  2. GQE miss → call ML, store in Redis GQE cache (7 days)
 *  3. FAISS search via ML service
 *  4. Store full result in Redis (30 min)
 *  5. Persist Query + Results to MongoDB  ← async, never blocks response
 */
router.post("/", protect, async (req, res) => {
  try {
    const { query, topK = 10, useGqe = true } = req.body;

    if (!query || typeof query !== "string" || query.trim().length === 0) {
      return res.status(400).json({ message: "query is required." });
    }

    const cleanQuery = query.trim();
    const userId     = req.user._id.toString();

    // ── Level 2: Full search cache ─────────────────────────────────────────
    const cachedResult = await getSearchCache(userId, cleanQuery);
    if (cachedResult) {
      // Persist to history async so the repeated search still appears
      persistToMongo(cleanQuery, userId, null, cachedResult.mlData).catch(() => {});
      return res.json({ ...cachedResult.response, fromCache: true });
    }

    let gqeData     = null;
    let searchPayload = {
      query:               cleanQuery,
      top_k:               topK,
      user_id:             userId,
      use_dynamic_weights: true,
    };

    // ── Level 1: GQE cache ─────────────────────────────────────────────────
    if (useGqe) {
      const cachedGqe = await getGqeCache(cleanQuery);
      if (cachedGqe) {
        // Cache hit: skip flan-t5 entirely
        gqeData = cachedGqe;
        searchPayload.representative_embeddings = gqeData.representative_embeddings;
        searchPayload.modality_weights          = gqeData.weights;
      } else {
        // Cache miss: call ML service (slow path, 5–30 s)
        try {
          const expandRes = await mlAxios.post(`/ml/query/expand`, { query: cleanQuery });
          gqeData = expandRes.data;
          searchPayload.representative_embeddings = gqeData.representative_embeddings;
          searchPayload.modality_weights          = gqeData.weights;
          // Store for 7 days — fire-and-forget
          setGqeCache(cleanQuery, gqeData).catch(() => {});
        } catch (expandErr) {
          console.warn("[Search] GQE failed, falling back to direct search:", expandErr.message);
        }
      }
    }

    // ── FAISS search ───────────────────────────────────────────────────────
    const mlResponse = await mlAxios.post(`/ml/search`, searchPayload);
    const mlData     = mlResponse.data;

    // ── Build response ─────────────────────────────────────────────────────
    const response = {
      queryId:         null,
      query:           cleanQuery,
      results:         mlData.results ?? [],
      modality:        mlData.modality,
      weights:         mlData.weights,
      totalCandidates: mlData.total_candidates,
      gqeApplied:      mlData.gqe_applied ?? false,
      variants:        gqeData?.variants ?? [],
      fromCache:       false,
    };

    // Cache full result for 30 min (fire-and-forget)
    setSearchCache(userId, cleanQuery, { response, mlData }).catch(() => {});

    // Persist to MongoDB in background — response goes out first
    persistToMongo(cleanQuery, userId, gqeData, mlData).catch(() => {});

    return res.json(response);

  } catch (err) {
    if (err.code === "ECONNREFUSED") {
      return res.status(503).json({
        message: "ML service is unavailable. Make sure it is running on port 8001.",
      });
    }
    res.status(500).json({ message: err.message });
  }
});

/**
 * Persist a search (Query + Results) to MongoDB.
 * Always runs in the background — never blocks the HTTP response.
 */
async function persistToMongo(cleanQuery, userId, gqeData, mlData) {
  try {
    const queryDoc = await Query.create({
      rawQuery:              cleanQuery,
      expandedVariants:      gqeData?.variants        ?? [],
      representativeQueries: gqeData?.representatives ?? [cleanQuery],
      predictedModality:     mlData.modality,
      modalityWeights:       mlData.weights,
      resultCount:           mlData.results?.length   ?? 0,
      searchedBy:            userId,
    });

    if (mlData.results?.length > 0) {
      const mongoose   = await import("mongoose");
      const resultDocs = mlData.results
        .filter((r) => r.video_id && mongoose.default.isValidObjectId(r.video_id))
        .map((r) => ({
          queryId:   queryDoc._id,
          rawQuery:  cleanQuery,
          videoId:   r.video_id,
          segmentId: mongoose.default.isValidObjectId(r.segment_id) ? r.segment_id : undefined,
          startTime: r.start_time,
          endTime:   r.end_time,
          rank:      r.rank,
          fusedScore: r.fused_score,
          evidence: {
            visualWeight:     r.modality_weights?.visual ?? 0,
            speechWeight:     r.modality_weights?.speech ?? 0,
            ocrWeight:        r.modality_weights?.ocr    ?? 0,
            visualSimilarity: r.visual_score ?? 0,
            speechSimilarity: r.speech_score ?? 0,
            ocrSimilarity:    r.ocr_score    ?? 0,
          },
          searchedBy: userId,
        }));

      if (resultDocs.length > 0) {
        await Result.insertMany(resultDocs);
        await Query.findByIdAndUpdate(queryDoc._id, { resultCount: resultDocs.length });
      }
    }
    return queryDoc._id;
  } catch (err) {
    console.error("[Search] MongoDB persist failed:", err.message);
    return null;
  }
}


/**
 * GET /api/search/history
 * Returns the authenticated user's past searches (newest first).
 * Query params: limit (default 20), page (default 1)
 */
router.get("/history", protect, async (req, res) => {
  try {
    const limit = Math.min(parseInt(req.query.limit) || 20, 50);
    const page = Math.max(parseInt(req.query.page) || 1, 1);
    const skip = (page - 1) * limit;

    const [queries, total] = await Promise.all([
      Query.find({ searchedBy: { $in: [req.user._id, null] } })
        .sort({ createdAt: -1 })
        .skip(skip)
        .limit(limit)
        .lean(),
      Query.countDocuments({ searchedBy: { $in: [req.user._id, null] } }),
    ]);

    // Attach top result (rank=1) for each query so the UI can show a preview
    const queryIds = queries.map((q) => q._id);
    const topResults = await Result.find({
      queryId: { $in: queryIds },
      rank: 1,
    })
      .populate("videoId", "title filename mimeType")
      .lean();

    // Map queryId → top result
    const resultMap = {};
    for (const r of topResults) {
      resultMap[r.queryId.toString()] = r;
    }

    const enriched = queries.map((q) => ({
      ...q,
      topResult: resultMap[q._id.toString()] ?? null,
    }));

    res.json({
      queries: enriched,
      total,
      page,
      pages: Math.ceil(total / limit),
    });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

/**
 * GET /api/search/history/:queryId
 * Returns the full result set for one past search.
 */
router.get("/history/:queryId", protect, async (req, res) => {
  try {
    const query = await Query.findOne({
      _id: req.params.queryId,
      searchedBy: { $in: [req.user._id, null] },
    }).lean();

    if (!query) {
      return res.status(404).json({ message: "Search not found." });
    }

    const results = await Result.find({ queryId: query._id })
      .sort({ rank: 1 })
      .populate("videoId", "title filename mimeType")
      .lean();

    res.json({ query, results });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

/**
 * DELETE /api/search/history/:queryId
 * Delete a saved search + its results from history.
 */
router.delete("/history/:queryId", protect, async (req, res) => {
  try {
    const query = await Query.findOneAndDelete({
      _id: req.params.queryId,
      searchedBy: { $in: [req.user._id, null] },
    });

    if (!query) {
      return res.status(404).json({ message: "Search not found." });
    }

    await Result.deleteMany({ queryId: req.params.queryId });
    res.json({ message: "Search deleted.", queryId: req.params.queryId });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});

export default router;
