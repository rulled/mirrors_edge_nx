#include "mirrorsedge_app.h"

#ifdef __SWITCH__
#include <switch.h>
extern "C" int __system_argc;
extern "C" char** __system_argv;
#include <sys/iosupport.h>
extern "C" const devoptab_t dotab_stdnull;
namespace {
const bool kArgvByDefault = [] {
  static char path[] = "sdmc:/switch/mirrorsedge-nx/mirrorsedge.nro";
  static char* argv[] = {path, nullptr};
  if (__system_argc <= 0 || !__system_argv || !__system_argv[0] || !__system_argv[0][0]) {
    __system_argc = 1;
    __system_argv = argv;
  }
  if (!devoptab_list[STD_OUT]) devoptab_list[STD_OUT] = &dotab_stdnull;
  if (!devoptab_list[STD_ERR]) devoptab_list[STD_ERR] = &dotab_stdnull;
  return true;
}();
}  // namespace
#endif

REX_DEFINE_APP(mirrorsedge, MirrorsEdgeApp::Create)
