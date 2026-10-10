import mongoose from "mongoose";
import bcrypt   from "bcryptjs";
import crypto   from "crypto";

/**
 * User — for JWT authentication.
 * Admin: can upload and manage videos
 * User: can only search
 *
 * Email verification: isVerified / emailVerifyToken / emailVerifyExpires
 * Password reset:     resetPasswordToken / resetPasswordExpires
 */
const userSchema = new mongoose.Schema(
  {
    name:  { type: String, required: true, trim: true },
    email: {
      type: String, required: true, unique: true,
      lowercase: true, trim: true,
    },
    passwordHash: { type: String, required: true },
    role: {
      type: String, enum: ["admin", "user"], default: "user",
    },

    // ── Email verification ──
    isVerified:         { type: Boolean, default: false },
    emailVerifyToken:   { type: String },
    emailVerifyExpires: { type: Date },

    // ── Password reset ──
    resetPasswordToken:   { type: String },
    resetPasswordExpires: { type: Date },
  },
  { timestamps: true }
);

/** Hash password before saving */
userSchema.pre("save", async function (next) {
  if (!this.isModified("passwordHash")) return next();
  this.passwordHash = await bcrypt.hash(this.passwordHash, 12);
  next();
});

/** Compare a plain password against the stored hash */
userSchema.methods.comparePassword = async function (plain) {
  return bcrypt.compare(plain, this.passwordHash);
};

/** Generate a cryptographically random token (hex, 32 bytes) */
userSchema.methods.createEmailVerifyToken = function () {
  const raw = crypto.randomBytes(32).toString("hex");
  // Store hashed version in DB, return raw to send in email
  this.emailVerifyToken   = crypto.createHash("sha256").update(raw).digest("hex");
  this.emailVerifyExpires = new Date(Date.now() + 24 * 60 * 60 * 1000); // 24h
  return raw;
};

userSchema.methods.createPasswordResetToken = function () {
  const raw = crypto.randomBytes(32).toString("hex");
  this.resetPasswordToken   = crypto.createHash("sha256").update(raw).digest("hex");
  this.resetPasswordExpires = new Date(Date.now() + 60 * 60 * 1000); // 1h
  return raw;
};

export default mongoose.model("User", userSchema);
