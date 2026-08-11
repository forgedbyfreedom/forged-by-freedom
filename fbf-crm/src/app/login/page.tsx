import Link from "next/link";
import { login, signup } from "./actions";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string; mode?: string }>;
}) {
  const { error, mode } = await searchParams;
  const isSignup = mode === "signup";

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-4">
      {/* Background glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 h-[500px] w-[500px] -translate-x-1/2 rounded-full opacity-30 blur-3xl"
        style={{ background: "radial-gradient(circle, #ff6a00 0%, transparent 60%)" }}
      />

      <div className="relative w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="fbf-eyebrow mb-3">Forged by Freedom</div>
          <h1 className="fbf-title-gradient text-4xl font-black tracking-tight">FBF CRM</h1>
          <div className="fbf-divider" />
          <p className="mt-4 text-sm text-muted-foreground">
            {isSignup ? "Create the owner account." : "Sign in to continue."}
          </p>
        </div>

        <div className="fbf-card !p-7">
          <form className="space-y-5">
            <div>
              <label
                htmlFor="email"
                className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
              >
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                required
                autoComplete="email"
                className="w-full rounded-md border border-border bg-surface-2 px-3 py-2.5 text-sm text-foreground outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary"
              />
            </div>
            <div>
              <label
                htmlFor="password"
                className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
              >
                Password
              </label>
              <input
                id="password"
                name="password"
                type="password"
                required
                autoComplete={isSignup ? "new-password" : "current-password"}
                className="w-full rounded-md border border-border bg-surface-2 px-3 py-2.5 text-sm text-foreground outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary"
              />
            </div>

            {error && (
              <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {error === "not_authorized"
                  ? "This email is not authorized."
                  : decodeURIComponent(error)}
              </p>
            )}

            <button
              formAction={isSignup ? signup : login}
              className="w-full rounded-md px-4 py-2.5 text-sm font-bold uppercase tracking-wider text-white shadow-fbf-btn transition-transform hover:scale-[1.01] active:scale-[0.99]"
              style={{
                background: "linear-gradient(135deg, #ff6a00, #ff8c00, #e85d00)",
              }}
            >
              {isSignup ? "Create Account" : "Sign In"}
            </button>
          </form>
        </div>

        <p className="mt-5 text-center text-xs text-muted-foreground">
          {isSignup ? (
            <Link href="/login" className="hover:text-primary">
              Have an account? <span className="underline">Sign in</span>
            </Link>
          ) : (
            <Link href="/login?mode=signup" className="hover:text-primary">
              First time? <span className="underline">Create the owner account</span>
            </Link>
          )}
        </p>
      </div>
    </main>
  );
}
