/**
 * sendOtpEmail  — sends a 6-digit OTP to the user's email before registration.
 * Used in the pre-registration verification step.
 */
import nodemailer from "nodemailer";

const createTransporter = () =>
  nodemailer.createTransport({
    host:   process.env.EMAIL_HOST || "smtp.gmail.com",
    port:   parseInt(process.env.EMAIL_PORT) || 587,
    secure: parseInt(process.env.EMAIL_PORT) === 465,
    auth: {
      user: process.env.EMAIL_USER,
      pass: process.env.EMAIL_PASS,
    },
  });

const FROM   = () => process.env.EMAIL_FROM || `MEGA Search <${process.env.EMAIL_USER}>`;
const CLIENT = () => process.env.CLIENT_URL  || "http://localhost:5173";

// ─── Shared HTML shell ────────────────────────────────────────────────────────
const shell = (body) => `
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/></head>
<body style="margin:0;padding:0;background:#f5f5f3;font-family:'Segoe UI',system-ui,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f3;padding:48px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:#fff;border:1px solid #e0e0da;border-radius:12px;overflow:hidden;max-width:100%;">
        <tr><td style="background:#0a0a0a;padding:24px 32px;">
          <span style="font-size:20px;font-weight:700;color:#fff;letter-spacing:-.03em;">◆ MEGA</span>
        </td></tr>
        <tr><td style="padding:36px 32px 28px;">${body}</td></tr>
        <tr><td style="padding:20px 32px;border-top:1px solid #f0f0ec;background:#fafaf8;">
          <p style="margin:0;font-size:12px;color:#9a9a9a;">
            Walchand College of Engineering, Sangli · B.Tech Project 2026–27
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>`;

// ─── 1. OTP email (pre-registration) ─────────────────────────────────────────
export async function sendOtpEmail(email, otp) {
  const html = shell(`
    <h1 style="margin:0 0 8px;font-size:24px;font-weight:700;color:#0a0a0a;letter-spacing:-.03em;">
      Verify your email
    </h1>
    <p style="font-size:15px;color:#4a4a4a;line-height:1.65;">
      Use the code below to verify your email address and complete your MEGA account registration.
    </p>
    <div style="margin:28px 0;text-align:center;">
      <span style="
        display:inline-block;
        font-size:42px;font-weight:800;letter-spacing:12px;
        color:#0a0a0a;background:#f5f5f3;
        padding:20px 32px;border-radius:12px;
        border:2px solid #e0e0da;font-family:monospace;">
        ${otp}
      </span>
    </div>
    <p style="margin:0;font-size:13px;color:#9a9a9a;">
      This code expires in <strong>10 minutes</strong>.
      If you didn't request this, you can safely ignore this email.
    </p>
  `);

  await createTransporter().sendMail({
    from:    FROM(),
    to:      email,
    subject: `${otp} is your MEGA verification code`,
    html,
  });
}

// ─── 2. Verification link email (post-registration) ──────────────────────────
export async function sendVerificationEmail(user, token) {
  const link = `${CLIENT()}/verify-email?token=${token}`;
  const html = shell(`
    <h1 style="margin:0 0 8px;font-size:24px;font-weight:700;color:#0a0a0a;">Verify your email</h1>
    <p style="font-size:15px;color:#4a4a4a;">Hi ${user.name},</p>
    <p style="font-size:15px;color:#4a4a4a;line-height:1.65;">
      Click the button below to verify your email address and activate your account.
    </p>
    <a href="${link}" style="display:inline-block;padding:12px 28px;background:#0a0a0a;color:#fff;
       border-radius:999px;text-decoration:none;font-size:14px;font-weight:600;margin-top:24px;">
      Verify email address
    </a>
    <p style="margin:20px 0 0;font-size:12px;color:#9a9a9a;">
      This link expires in <strong>24 hours</strong>.
    </p>
  `);

  await createTransporter().sendMail({
    from:    FROM(),
    to:      user.email,
    subject: "Verify your MEGA account",
    html,
  });
}

// ─── 3. Password reset email ──────────────────────────────────────────────────
export async function sendPasswordResetEmail(user, token) {
  const link = `${CLIENT()}/reset-password?token=${token}`;
  const html = shell(`
    <h1 style="margin:0 0 8px;font-size:24px;font-weight:700;color:#0a0a0a;">Reset your password</h1>
    <p style="font-size:15px;color:#4a4a4a;">Hi ${user.name},</p>
    <p style="font-size:15px;color:#4a4a4a;line-height:1.65;">
      We received a request to reset your MEGA account password.
    </p>
    <a href="${link}" style="display:inline-block;padding:12px 28px;background:#0a0a0a;color:#fff;
       border-radius:999px;text-decoration:none;font-size:14px;font-weight:600;margin-top:24px;">
      Reset password
    </a>
    <p style="margin:20px 0 0;font-size:12px;color:#9a9a9a;">
      This link expires in <strong>1 hour</strong>.
      If you didn't request a reset, ignore this email.
    </p>
  `);

  await createTransporter().sendMail({
    from:    FROM(),
    to:      user.email,
    subject: "Reset your MEGA password",
    html,
  });
}
