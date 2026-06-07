"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ArrowLeft, Loader2 } from "lucide-react";
import { supabase } from "@/lib/supabase";

function AuthContent() {
  const params = useSearchParams();
  const router = useRouter();
  const mode = params.get("mode") === "signin" ? "signin" : "signup";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) {
        router.replace("/dashboard");
      }
    });
  }, [router]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      const result =
        mode === "signin"
          ? await supabase.auth.signInWithPassword({ email, password })
          : await supabase.auth.signUp({
              email,
              password,
              options: {
                data: {
                  first_name: firstName.trim(),
                  last_name: lastName.trim(),
                },
              },
            });
      if (result.error) {
        setMessage(result.error.message);
        return;
      }
      if (result.data.session) {
        router.replace("/dashboard");
      } else {
        setMessage("Account created. Confirm your email, then sign in.");
        router.replace("/auth?mode=signin");
      }
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to reach authentication service. Check your connection and try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="grid min-h-screen place-items-center px-6 py-10">
      <div className="w-full max-w-md">
        <Link className="mb-6 inline-flex items-center gap-2 font-bold text-[var(--accent)]" href="/">
          <ArrowLeft size={18} /> Back to Sway
        </Link>
        <section className="panel p-6 shadow-lg">
          <h1 className="text-3xl font-black">{mode === "signin" ? "Log in" : "Create account"}</h1>
          <p className="mt-2 text-[#667085]">Use your Sway account to open the web dashboard.</p>
          <div className="mt-6 grid grid-cols-2 gap-2 rounded-lg bg-[#f1eadf] p-1">
            <Link
              className={`rounded-md px-3 py-2 text-center font-bold ${mode === "signup" ? "bg-white text-[var(--accent)]" : "text-[#667085]"}`}
              href="/auth?mode=signup"
            >
              Create
            </Link>
            <Link
              className={`rounded-md px-3 py-2 text-center font-bold ${mode === "signin" ? "bg-white text-[var(--accent)]" : "text-[#667085]"}`}
              href="/auth?mode=signin"
            >
              Log in
            </Link>
          </div>
          <form className="mt-6 space-y-4" onSubmit={submit}>
            {mode === "signup" ? (
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="mb-2 block text-sm font-bold">First name</span>
                  <input className="field" maxLength={80} onChange={(e) => setFirstName(e.target.value)} required value={firstName} />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm font-bold">Last name</span>
                  <input className="field" maxLength={80} onChange={(e) => setLastName(e.target.value)} required value={lastName} />
                </label>
              </div>
            ) : null}
            <label className="block">
              <span className="mb-2 block text-sm font-bold">Email</span>
              <input className="field" onChange={(e) => setEmail(e.target.value)} required type="email" value={email} />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-bold">Password</span>
              <input className="field" minLength={6} onChange={(e) => setPassword(e.target.value)} required type="password" value={password} />
            </label>
            {message ? <p className="rounded-lg bg-[#fff2e8] p-3 text-sm font-bold text-[#9a3412]">{message}</p> : null}
            <button className="btn btn-primary w-full" disabled={loading} type="submit">
              {loading ? <Loader2 className="animate-spin" size={18} /> : null}
              {mode === "signin" ? "Log in" : "Create account"}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
}

export default function AuthPage() {
  return (
    <Suspense>
      <AuthContent />
    </Suspense>
  );
}
