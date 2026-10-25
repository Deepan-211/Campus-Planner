"use client";

import React, { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { CampusMapProps } from "./CampusMapLeaflet";

// Dynamically import Leaflet map with SSR disabled to guarantee no server-side window errors
const CampusMapLeaflet = dynamic(() => import("./CampusMapLeaflet"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full min-h-[400px] rounded-2xl glass-card flex items-center justify-center text-zinc-400 font-classic text-sm animate-pulse border border-white/10 bg-zinc-950">
      <div className="flex flex-col items-center gap-3">
        <div className="w-6 h-6 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
        <span>Loading Campus Digital Twin Map & Tiles...</span>
      </div>
    </div>
  ),
});

export default function CampusMap(props: CampusMapProps) {
  const [isMounted, setIsMounted] = useState<boolean>(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  if (!isMounted) {
    return (
      <div
        className={`w-full overflow-hidden relative shadow-md ${
          props.className || "h-[520px] rounded-2xl border border-white/10 bg-black"
        }`}
        style={{ height: props.height || "520px" }}
      >
        <div className="w-full h-full flex items-center justify-center text-zinc-400 font-classic text-sm animate-pulse">
          <div className="flex flex-col items-center gap-3">
            <div className="w-6 h-6 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" />
            <span>Initializing Campus Digital Twin Map...</span>
          </div>
        </div>
      </div>
    );
  }

  return <CampusMapLeaflet {...props} />;
}
