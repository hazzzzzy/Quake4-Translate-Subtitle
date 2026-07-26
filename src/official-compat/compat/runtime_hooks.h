#pragma once

#include <cstdint>
#include <filesystem>
#include <ostream>

namespace q4cn {

void SetRuntimeLogPath(const std::filesystem::path& path);
bool InstallRuntimeHooks(std::uint8_t* moduleBase, std::ostream& log);

}  // namespace q4cn
