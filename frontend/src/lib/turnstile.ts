export async function verifyTurnstileToken(token: string) {
  // Skip validation in development if no secret key is provided
  if (process.env.NODE_ENV === "development" && !process.env.TURNSTILE_SECRET_KEY) {
    console.warn("Turnstile validation skipped in development. Set TURNSTILE_SECRET_KEY to enable validation.");
    return true;
  }

  try {
    const formData = new URLSearchParams();
    formData.append("secret", process.env.TURNSTILE_SECRET_KEY || "");
    formData.append("response", token);
    
    const response = await fetch(
      "https://challenges.cloudflare.com/turnstile/v0/siteverify",
      {
        method: "POST",
        body: formData.toString(),
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      }
    );

    const data = await response.json();
    return data.success === true;
  } catch (error) {
    console.error("Turnstile verification error:", error);
    return false;
  }
}