#pragma once
/*
 * masseffect_diag_draw_trace (2026-10-21, Mirror's Edge black 3D).
 *
 * One frame of the PM4 stream, as lines: every draw with its color/depth target (EDRAM base and
 * format), surface pitch, pixel shader number, topology, vertex count and the textures it samples.
 * It exists because the resolved-target report shows which guest addresses were written, but not the
 * order of the passes and not what a full-screen pass reads: with "3D black, UI visible" the question
 * is whether a pass reads the scene target and writes the front buffer at all, and with which shader.
 *
 * Written on the PM4 ring thread only (the one that records draws), so no lock. The window is opened
 * and closed by NoteSwap (me_draw_trace seconds after the renderer starts), and the buffer is capped.
 */
#include <atomic>
#include <string>

namespace me::native::draw_trace {

inline std::atomic<bool> g_on{false};
inline std::string g_text;
inline uint32_t g_draws = 0;

inline bool On() { return g_on.load(std::memory_order_relaxed); }

inline void Begin() {
  g_text.clear();
  g_draws = 0;
  g_on.store(true, std::memory_order_relaxed);
}

// Returns the finished frame and closes the window.
inline std::string End() {
  g_on.store(false, std::memory_order_relaxed);
  std::string out;
  out.swap(g_text);
  return out;
}

inline void Add(const std::string& line) {
  if (g_text.size() > 400000) return;  // bound: a third of the log budget
  g_text += line;
  g_text += '\n';
  ++g_draws;
}

}  // namespace me::native::draw_trace

namespace me::native::frame_dump {

inline std::atomic<bool> g_requested{false};
inline std::atomic<bool> g_active{false};
inline uint32_t g_sequence = 0;
inline std::string g_folder;

inline void Request() {
  g_requested.store(true, std::memory_order_release);
}

inline bool IsRequested() {
  return g_requested.load(std::memory_order_acquire);
}

inline bool IsActive() {
  return g_active.load(std::memory_order_relaxed);
}

}  // namespace me::native::frame_dump
