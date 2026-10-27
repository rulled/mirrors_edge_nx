#pragma once

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <string>
#include <memory>

#include <rex/cvar.h>
#include <rex/filesystem.h>
#include <rex/logging.h>
#include <rex/runtime.h>
#include <rex/rex_app.h>

#if REX_PLATFORM_SWITCH
extern "C" {
void RexSwitchApmRequestGpuMhz(int mhz);
void RexSwitchApmApply(void);
}
#endif

#include "generated/default/mirrorsedge_init.h"
#include "native/me_native_system.h"

class MirrorsEdgeApp : public rex::ReXApp {
 public:
  using rex::ReXApp::ReXApp;

  static std::unique_ptr<rex::ui::WindowedApp> Create(
      rex::ui::WindowedAppContext& ctx) {
    return std::unique_ptr<MirrorsEdgeApp>(new MirrorsEdgeApp(ctx, "mirrorsedge", PPCImageConfig));
  }

  void OnConfigurePaths(rex::PathConfig& paths) override {
    if (paths.game_data_root.empty()) {
      std::error_code ec;
      const auto folder = rex::filesystem::GetExecutableFolder();
      const std::filesystem::path candidates[] = {
        folder / "game_root",
        folder,
        "sdmc:/switch/mirrorsedge-nx/game_root",
        "sdmc:/switch/mirrorsedge-nx",
        "romfs:/game_root",
        "romfs:/"
      };
      for (const auto& c : candidates) {
        if (!c.empty() && std::filesystem::is_directory(c, ec)) {
          if (std::filesystem::exists(c / "default.xex", ec) ||
              std::filesystem::exists(c / "TdGame", ec)) {
            paths.game_data_root = c;
            break;
          }
        }
      }
    }

    if (paths.user_data_root.empty()) {
      paths.user_data_root = "sdmc:/switch/mirrorsedge-nx";
    }
    if (paths.cache_root.empty()) {
      paths.cache_root = "sdmc:/switch/mirrorsedge-nx/cache";
    }
    if (paths.config_path.empty() || !std::filesystem::exists(paths.config_path)) {
      paths.config_path = "sdmc:/switch/mirrorsedge-nx/mirrorsedge.toml";
    }
  }

  void OnPreSetup(rex::RuntimeConfig& config) override {
#if REX_PLATFORM_SWITCH
    // Request official 460.8 MHz handheld GPU clock
    RexSwitchApmRequestGpuMhz(460);
    RexSwitchApmApply();
#endif
    if (me::native::Enabled()) {
      config.graphics = me::native::CreateGraphicsSystem();
      config.gpu_plugin.clear();
      REXLOG_INFO("[gpu] Using native Vulkan renderer (PM4 ring)");
    }
  }

  void OnPostInitLogging() override {
    REXLOG_INFO("Mirror's Edge NX (Xbox 360 Static Recompilation for Nintendo Switch)");
    REXLOG_INFO("[paths] game_data_root: {}", game_data_root().string());
    REXLOG_INFO("[paths] user_data_root: {}", user_data_root().string());

    if (me::native::Enabled()) {
      REXLOG_INFO("[gpu] Native Vulkan renderer active (no desktop Xenos emulation)");
    } else if (!rex::cvar::HasNonDefaultValue("gpu_plugin")) {
      rex::cvar::SetFlagByName("gpu_plugin", "xenos");
      REXLOG_INFO("[gpu] Selected fallback GPU plugin: xenos");
    }
  }
};
