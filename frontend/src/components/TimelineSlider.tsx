"use client";

import React, { useState, useEffect } from "react";
import { Play, Pause, RotateCcw, FastForward, Clock } from "lucide-react";

export default function TimelineSlider({
  selectedHour,
  onHourChange,
  totalBikes = 100,
}: {
  selectedHour: number;
  onHourChange: (hour: number) => void;
  totalBikes?: number;
}) {
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [speed, setSpeed] = useState<number>(1000); // 1 second per hour

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (isPlaying) {
      interval = setInterval(() => {
        onHourChange(selectedHour >= 22 ? 7 : selectedHour + 1);
      }, speed);
    }
    return () => clearInterval(interval);
  }, [isPlaying, selectedHour, speed, onHourChange]);

  const formatHour = (h: number) => {
    const period = h >= 12 ? "PM" : "AM";
    const displayHour = h > 12 ? h - 12 : h === 0 ? 12 : h;
    return `${displayHour}:00 ${period}`;
  };

  const isRushHour =
    (selectedHour >= 8 && selectedHour <= 10) ||
    (selectedHour >= 16 && selectedHour <= 18);

  return (
    <div className="glass-card p-4 rounded-2xl flex flex-col justify-between h-full">
      {/* Header and Status */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-zinc-300" />
          <span className="text-xs font-classic font-bold text-white tracking-widest uppercase">
            Simulation Timeline
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          {isRushHour ? (
            <span className="text-[10px] font-classic px-2 py-0.5 rounded-full bg-white text-black font-bold animate-pulse">
              BELL RUSH :50-:05
            </span>
          ) : (
            <span className="text-[10px] font-classic text-zinc-400 px-2 py-0.5 rounded-full bg-white/[0.05] border border-white/10 uppercase">
              OFF-PEAK
            </span>
          )}
        </div>
      </div>

      {/* Media Player Scrubber Body (matching reference music player style) */}
      <div className="flex items-center gap-3.5 my-auto">
        {/* Play/Pause Square Widget (like album art in reference) */}
        <button
          onClick={() => setIsPlaying(!isPlaying)}
          className={`w-14 h-14 rounded-2xl flex flex-col items-center justify-center shrink-0 transition shadow-lg ${
            isPlaying
              ? "bg-white text-black hover:bg-zinc-200"
              : "bg-zinc-900 border border-white/20 text-white hover:border-white/50"
          }`}
          title={isPlaying ? "Pause Timeline" : "Play Timeline"}
        >
          {isPlaying ? (
            <Pause className="w-6 h-6 fill-current" />
          ) : (
            <Play className="w-6 h-6 fill-current ml-0.5" />
          )}
          <span className="text-[9px] font-mono font-bold mt-0.5">
            {isPlaying ? "PAUSE" : "PLAY"}
          </span>
        </button>

        {/* Time and Slider Details */}
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline justify-between mb-1.5">
            <span className="text-sm font-bold text-white font-mono">
              {formatHour(selectedHour)}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => {
                  setIsPlaying(false);
                  onHourChange(7);
                }}
                className="p-1 text-zinc-400 hover:text-white rounded hover:bg-white/10 transition"
                title="Reset to 07:00 AM"
              >
                <RotateCcw className="w-3 h-3" />
              </button>
              <button
                onClick={() => setSpeed(speed === 1000 ? 500 : 1000)}
                className="text-[10px] font-mono px-1.5 py-0.5 text-zinc-400 hover:text-white rounded hover:bg-white/10 transition"
                title="Toggle playback speed"
              >
                {speed === 1000 ? "1x" : "2x"}
              </button>
            </div>
          </div>

          {/* Scrubber Range Slider */}
          <div className="relative flex items-center">
            <input
              type="range"
              min={7}
              max={22}
              step={1}
              value={selectedHour}
              onChange={(e) => onHourChange(Number(e.target.value))}
              className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-white hover:accent-zinc-300 transition"
            />
          </div>

          <div className="flex justify-between items-center text-[9px] font-mono text-zinc-500 mt-1">
            <span>07:00 AM</span>
            <span>12:00 PM</span>
            <span>22:00 PM</span>
          </div>
        </div>
      </div>

      {/* Footer Pill */}
      <div className="mt-2 pt-2 border-t border-white/[0.08] flex items-center justify-between text-[10px] text-zinc-400 font-mono">
        <span>Window: 15 Operating Hours</span>
        <span className="text-zinc-300">{totalBikes} Bicycles Simulated</span>
      </div>
    </div>
  );
}
