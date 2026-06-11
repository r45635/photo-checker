"use client"

import { useState } from "react"
import { Play, ImageOff } from "lucide-react"

interface VideoPlayerProps {
  videoSrc: string
  posterSrc: string
  className?: string
}

export default function VideoPlayer({ videoSrc, posterSrc, className = "" }: VideoPlayerProps) {
  const [playing, setPlaying] = useState(false)
  const [posterError, setPosterError] = useState(false)
  const [videoError, setVideoError] = useState(false)

  if (playing) {
    if (videoError) {
      return (
        <div className={`flex flex-col items-center justify-center gap-2 text-[#4a6080] ${className}`}>
          <ImageOff size={32} />
          <span className="text-xs">Playback unavailable</span>
        </div>
      )
    }
    return (
      <video
        autoPlay
        controls
        className={`object-contain bg-black ${className}`}
        onError={() => setVideoError(true)}
      >
        <source src={videoSrc} type="video/mp4" />
        <source src={videoSrc} type="video/quicktime" />
      </video>
    )
  }

  return (
    <div
      className={`relative cursor-pointer group/vp ${className}`}
      onClick={() => setPlaying(true)}
    >
      {posterError ? (
        <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-[#4a6080]">
          <ImageOff size={32} />
        </div>
      ) : (
        <img
          src={posterSrc}
          className="w-full h-full object-contain"
          onError={() => setPosterError(true)}
          alt=""
        />
      )}
      {/* Play overlay */}
      <div className="absolute inset-0 flex items-center justify-center bg-black/25 group-hover/vp:bg-black/40 transition-colors duration-150">
        <div className="w-16 h-16 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center group-hover/vp:scale-110 transition-transform duration-150">
          <Play size={28} className="text-white ml-1.5" fill="white" />
        </div>
      </div>
    </div>
  )
}
