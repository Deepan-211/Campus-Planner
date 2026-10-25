import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CampusRide Planner | Digital Twin for UC Berkeley Micromobility",
  description:
    "Production-grade digital twin for university micromobility. Spatiotemporal forecasting, MILP morning allocation, OR-Tools vehicle routing, and SimPy discrete-event evaluation.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#090d16] text-slate-100 antialiased selection:bg-indigo-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
