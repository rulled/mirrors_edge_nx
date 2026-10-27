#include <rex/cvar.h>
#include <cstdint>

REXCVAR_DEFINE_BOOL(masseffect_vblank_sleep_exact, true, "Mass Effect", "vblank sleep")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(masseffect_scene_width, 0, "Mass Effect", "render width")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(masseffect_scene_height, 0, "Mass Effect", "render height")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_INT32(masseffect_scene_parts, 0xFF, "Mass Effect", "render parts")
    .lifecycle(rex::cvar::Lifecycle::kInitOnly);

namespace me::native {
void NotifyRingProgress() {}
}

extern "C" bool MeResolutionOutputSize(uint32_t*, uint32_t*) { return false; }
