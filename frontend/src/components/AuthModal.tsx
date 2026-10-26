"use client";

import React, { useState } from "react";
import { X, Lock, Mail, User, ShieldCheck, ArrowRight, Loader2, KeyRound, Check } from "lucide-react";
import { loginUser, registerUser } from "../lib/api";
import { UserProfile } from "../lib/types";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: UserProfile) => void;
}

export default function AuthModal({ isOpen, onClose, onSuccess }: AuthModalProps) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState<"admin" | "operator" | "student">("operator");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Close on Escape key (hook must always run before any return)
  React.useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      if (mode === "login") {
        const res = await loginUser(email, password);
        onSuccess(res.user);
        onClose();
      } else {
        if (!fullName.trim()) {
          setError("Please provide your full name.");
          setIsLoading(false);
          return;
        }
        const res = await registerUser(email, password, fullName, role);
        onSuccess(res.user);
        onClose();
      }
    } catch (err: any) {
      setError(err?.message || "Authentication failed. Please verify credentials.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoLogin = async (demoEmail: string, demoPass: string) => {
    setIsLoading(true);
    setError(null);
    setEmail(demoEmail);
    setPassword(demoPass);
    try {
      const res = await loginUser(demoEmail, demoPass);
      onSuccess(res.user);
      onClose();
    } catch (err: any) {
      setError(err?.message || "Demo login failed.");
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
      onClick={onClose}
    >
      <div 
        className="relative w-full max-w-md bg-white rounded-3xl shadow-2xl border border-zinc-200 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Header Banner */}
        <div className="bg-gradient-to-r from-zinc-900 via-zinc-800 to-zinc-900 px-6 py-6 text-white relative">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1.5 rounded-full bg-white/10 hover:bg-white/20 text-zinc-300 hover:text-white transition"
          >
            <X className="w-4 h-4" />
          </button>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-zinc-800/80 border border-zinc-700 text-xs font-medium text-emerald-400 mb-2">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>FastAPI JWT Auth</span>
          </div>
          <h2 className="text-xl font-bold tracking-tight">
            {mode === "login" ? "Sign In to CampusRide" : "Create Operator Account"}
          </h2>
          <p className="text-xs text-zinc-400 mt-0.5">
            {mode === "login"
              ? "Access telemetry, fleet controls, and algorithmic rebalancing"
              : "Register to manage campus mobility and live dispatch"}
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-zinc-200 bg-zinc-50/70 p-1.5 gap-1.5">
          <button
            type="button"
            onClick={() => { setMode("login"); setError(null); }}
            className={`flex-1 py-2 text-xs font-semibold rounded-xl transition ${
              mode === "login"
                ? "bg-white text-zinc-900 shadow-sm border border-zinc-200"
                : "text-zinc-500 hover:text-zinc-800"
            }`}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => { setMode("register"); setError(null); }}
            className={`flex-1 py-2 text-xs font-semibold rounded-xl transition ${
              mode === "register"
                ? "bg-white text-zinc-900 shadow-sm border border-zinc-200"
                : "text-zinc-500 hover:text-zinc-800"
            }`}
          >
            Register Account
          </button>
        </div>

        {/* Form Body */}
        <div className="p-6">
          {error && (
            <div className="mb-4 p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-xl flex items-center gap-2">
              <span className="font-semibold">Error:</span> {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && (
              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1">Full Name</label>
                <div className="relative">
                  <User className="w-4 h-4 text-zinc-400 absolute left-3 top-2.5" />
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Deepan"
                    className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-zinc-300 focus:outline-none focus:ring-2 focus:ring-zinc-800 focus:border-transparent"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-zinc-700 mb-1">Email Address</label>
              <div className="relative">
                <Mail className="w-4 h-4 text-zinc-400 absolute left-3 top-2.5" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@campusride.edu"
                  className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-zinc-300 focus:outline-none focus:ring-2 focus:ring-zinc-800 focus:border-transparent"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-700 mb-1">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-zinc-400 absolute left-3 top-2.5" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-9 pr-3 py-2 text-xs rounded-xl border border-zinc-300 focus:outline-none focus:ring-2 focus:ring-zinc-800 focus:border-transparent"
                />
              </div>
            </div>

            {mode === "register" && (
              <div>
                <label className="block text-xs font-medium text-zinc-700 mb-1.5">Select Role</label>
                <div className="grid grid-cols-3 gap-2">
                  {(["operator", "admin", "student"] as const).map((r) => (
                    <button
                      type="button"
                      key={r}
                      onClick={() => setRole(r)}
                      className={`py-1.5 px-2 text-[11px] font-semibold rounded-lg border capitalize transition flex items-center justify-center gap-1 ${
                        role === r
                          ? "bg-zinc-900 text-white border-zinc-900 shadow-sm"
                          : "bg-white text-zinc-600 border-zinc-200 hover:bg-zinc-50"
                      }`}
                    >
                      {role === r && <Check className="w-3 h-3 text-emerald-400" />}
                      {r}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="w-full mt-2 py-2.5 px-4 bg-zinc-900 hover:bg-zinc-800 text-white font-semibold text-xs rounded-xl shadow-md transition flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Authenticating...</span>
                </>
              ) : (
                <>
                  <span>{mode === "login" ? "Sign In" : "Create Account"}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Logins */}
          <div className="mt-5 pt-4 border-t border-zinc-100">
            <p className="text-[11px] text-zinc-500 font-medium mb-2.5 flex items-center gap-1.5">
              <KeyRound className="w-3.5 h-3.5 text-zinc-400" />
              <span>Or sign in with 1-click demo profiles:</span>
            </p>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                disabled={isLoading}
                onClick={() => handleDemoLogin("admin@campusride.edu", "Admin@123")}
                className="py-1.5 px-2 bg-zinc-100 hover:bg-zinc-200 border border-zinc-200 text-zinc-800 rounded-lg text-[11px] font-medium transition text-center"
              >
                Admin
              </button>
              <button
                type="button"
                disabled={isLoading}
                onClick={() => handleDemoLogin("operator@campusride.edu", "Operator@123")}
                className="py-1.5 px-2 bg-zinc-100 hover:bg-zinc-200 border border-zinc-200 text-zinc-800 rounded-lg text-[11px] font-medium transition text-center"
              >
                Operator
              </button>
              <button
                type="button"
                disabled={isLoading}
                onClick={() => handleDemoLogin("student@campusride.edu", "Student@123")}
                className="py-1.5 px-2 bg-zinc-100 hover:bg-zinc-200 border border-zinc-200 text-zinc-800 rounded-lg text-[11px] font-medium transition text-center"
              >
                Student
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
