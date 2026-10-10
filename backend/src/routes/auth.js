import express from "express";
import jwt     from "jsonwebtoken";
import crypto  from "crypto";
import User    from "../models/User.js";
import {
  sendOtpEmail,
  sendVerificationEmail,
  sendPasswordResetEmail,
} from "../utils/email.js";

const router = express.Router();

/** Generate a signed JWT */
const signToken = (userId) =>
  jwt.sign({ id: userId }, process.env.JWT_SECRET, {
    expiresIn: process.env.JWT_EXPIRES_IN || "7d",
  });

const hashToken = (raw) =>
  crypto.createHash("sha256").update(raw).digest("hex");

// ─── In-memory OTP store { email → { otp, expiresAt, name, passwordHash } } ──
// Using a Map is fine for dev. For production, use Redis with TTL.
const otpStore = new Map();

// Auto-clean expired OTPs every 5 minutes
setInterval(() => {
  const now = Date.now();
  for (const [email, data] of otpStore) {
    if (data.expiresAt < now) otpStore.delete(email);
  }
}, 5 * 60 * 1000);


/**
 * POST /api/auth/send-otp
 * Step 1 of registration: send a 6-digit OTP to the email.
 * Body: { name, email, password }
 */
router.post("/send-otp", async (req, res) => {
  try {
    const { name, email, password } = req.body;

    if (!name || !email || !password) {
      return res.status(400).json({ message: "name, email, and password are required." });
    }
    if (password.length < 6) {
      return res.status(400).json({ message: "Password must be at least 6 characters." });
    }

    // Check if email is already registered
    const existing = await User.findOne({ email: email.toLowerCase().trim() });
    if (existing) {
      return res.status(409).json({ message: "Email already registered." });
    }

    // Generate 6-digit OTP
    const otp = String(Math.floor(100000 + Math.random() * 900000));

    // Store OTP + user data temporarily (10 min expiry)
    otpStore.set(email.toLowerCase().trim(), {
      otp,
      name,
      password,       // plain — will be hashed on actual User.create
      expiresAt: Date.now() + 10 * 60 * 1000,
    });

    // Send OTP email
    await sendOtpEmail(email, otp);

    res.json({ message: "OTP sent to your email. It expires in 10 minutes." });
  } catch (err) {
    console.error("[Auth] send-otp error:", err.message);
    res.status(500).json({ message: "Failed to send OTP. " + err.message });
  }
});


/**
 * POST /api/auth/register
 * Step 2: verify OTP and create the account.
 * Body: { email, otp }
 */
router.post("/register", async (req, res) => {
  try {
    const { email, otp } = req.body;

    if (!email || !otp) {
      return res.status(400).json({ message: "email and otp are required." });
    }

    const key     = email.toLowerCase().trim();
    const pending = otpStore.get(key);

    if (!pending) {
      return res.status(400).json({ message: "No OTP found for this email. Please request a new one." });
    }
    if (Date.now() > pending.expiresAt) {
      otpStore.delete(key);
      return res.status(400).json({ message: "OTP has expired. Please request a new one." });
    }
    if (pending.otp !== otp.trim()) {
      return res.status(400).json({ message: "Incorrect OTP. Please try again." });
    }

    // OTP verified — create the user account
    otpStore.delete(key);

    const existing = await User.findOne({ email: key });
    if (existing) {
      return res.status(409).json({ message: "Email already registered." });
    }

    const user = await User.create({
      name:         pending.name,
      email:        key,
      passwordHash: pending.password,
      isVerified:   true,   // OTP already verified the email
    });

    const token = signToken(user._id);

    res.status(201).json({
      token,
      user: { id: user._id, name: user.name, email: user.email, role: user.role, isVerified: true },
      message: "Account created successfully.",
    });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});


/**
 * POST /api/auth/register-admin
 */
router.post("/register-admin", async (req, res) => {
  try {
    const { name, email, password } = req.body;
    if (!name || !email || !password) {
      return res.status(400).json({ message: "name, email, and password are required." });
    }
    const existing = await User.findOne({ email });
    if (existing) {
      const updated = await User.findOneAndUpdate(
        { email }, { $set: { role: "admin" } }, { new: true }
      );
      return res.json({
        token: signToken(updated._id),
        user:  { id: updated._id, name: updated.name, email: updated.email, role: updated.role },
        message: "Existing account promoted to admin.",
      });
    }
    const user  = await User.create({ name, email, passwordHash: password, role: "admin", isVerified: true });
    res.status(201).json({
      token: signToken(user._id),
      user:  { id: user._id, name: user.name, email: user.email, role: user.role },
    });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});


/**
 * GET /api/auth/verify-email?token=<rawToken>
 */
router.get("/verify-email", async (req, res) => {
  try {
    const { token } = req.query;
    if (!token) return res.status(400).json({ message: "Token is required." });
    const hashed = hashToken(token);
    const user   = await User.findOne({
      emailVerifyToken:   hashed,
      emailVerifyExpires: { $gt: Date.now() },
    });
    if (!user) return res.status(400).json({ message: "Token is invalid or has expired." });
    user.isVerified         = true;
    user.emailVerifyToken   = undefined;
    user.emailVerifyExpires = undefined;
    await user.save({ validateBeforeSave: false });
    res.json({ message: "Email verified successfully. You can now log in." });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});


/**
 * POST /api/auth/login
 */
router.post("/login", async (req, res) => {
  try {
    const { email, password } = req.body;
    if (!email || !password) {
      return res.status(400).json({ message: "email and password are required." });
    }
    const user = await User.findOne({ email });
    if (!user || !(await user.comparePassword(password))) {
      return res.status(401).json({ message: "Invalid email or password." });
    }
    res.json({
      token: signToken(user._id),
      user:  { id: user._id, name: user.name, email: user.email, role: user.role, isVerified: user.isVerified },
    });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});


/**
 * POST /api/auth/forgot-password
 */
router.post("/forgot-password", async (req, res) => {
  try {
    const { email } = req.body;
    if (!email) return res.status(400).json({ message: "email is required." });
    const user = await User.findOne({ email });
    if (!user) return res.json({ message: "If that email exists, a reset link has been sent." });
    const rawToken = user.createPasswordResetToken();
    await user.save({ validateBeforeSave: false });
    sendPasswordResetEmail(user, rawToken).catch((e) =>
      console.error("[Auth] sendPasswordResetEmail failed:", e.message)
    );
    res.json({ message: "If that email exists, a reset link has been sent." });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});


/**
 * POST /api/auth/reset-password
 */
router.post("/reset-password", async (req, res) => {
  try {
    const { token, password } = req.body;
    if (!token || !password) {
      return res.status(400).json({ message: "token and password are required." });
    }
    const hashed = hashToken(token);
    const user   = await User.findOne({
      resetPasswordToken:   hashed,
      resetPasswordExpires: { $gt: Date.now() },
    });
    if (!user) return res.status(400).json({ message: "Token is invalid or has expired." });
    user.passwordHash         = password;
    user.resetPasswordToken   = undefined;
    user.resetPasswordExpires = undefined;
    await user.save();
    res.json({ message: "Password reset successfully. You can now log in." });
  } catch (err) {
    res.status(500).json({ message: err.message });
  }
});


export default router;
