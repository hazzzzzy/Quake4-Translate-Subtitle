#include "runtime_hooks.h"

#include <windows.h>

#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <limits>
#include <string>

#include "version_142.h"

namespace q4cn {
namespace {

constexpr std::size_t kFontInfoExSize = 0x6C9C;
constexpr std::size_t kActiveFontOffset = 0x28;
constexpr std::size_t kUseFontOffset = 0x2C;
constexpr std::size_t kGlyphRecordSize = 36;
constexpr std::size_t kGlyphScaleOffset = 0x2400;
constexpr unsigned char kLeadStart = 0x80;
constexpr unsigned char kLeadEnd = 0x9F;
constexpr unsigned char kTrailStart = 0xA0;
constexpr unsigned char kTrailEnd = 0xFF;
constexpr std::size_t kPageCount = 32;

struct Vec4 {
    float values[4];
};

using SetupFontsFunction = void(__thiscall*)(void* self);
using FindFontFunction = int(__thiscall*)(void* self, const char* name);
using DrawTextFunction = int(__thiscall*)(
    void* self,
    float x,
    float y,
    float scale,
    Vec4 color,
    const char* text,
    float adjust,
    int limit,
    int style,
    int cursor,
    int ravenFlag);

std::uint8_t* gModuleBase = nullptr;
SetupFontsFunction gOriginalSetupFonts = nullptr;
FindFontFunction gFindFont = nullptr;
DrawTextFunction gOriginalDrawText = nullptr;
std::array<int, kPageCount> gPageFontIndexes{};
std::filesystem::path gLogPath;

template <typename Function>
Function FunctionFromAddress(void* address) {
    static_assert(sizeof(Function) == sizeof(address));
    Function function = nullptr;
    std::memcpy(&function, &address, sizeof(function));
    return function;
}

template <typename Function>
std::uintptr_t FunctionAddress(Function function) {
    static_assert(sizeof(Function) == sizeof(std::uintptr_t));
    std::uintptr_t address = 0;
    std::memcpy(&address, &function, sizeof(address));
    return address;
}

void AppendRuntimeLog(const std::string& line) {
    if (gLogPath.empty()) {
        return;
    }
    std::ofstream log(gLogPath, std::ios::out | std::ios::app);
    if (log) {
        log << line << '\n';
    }
}

bool WriteRelativeJump(
    std::uint8_t* source,
    std::uintptr_t destination,
    std::string& error) {
    const auto nextInstruction =
        reinterpret_cast<std::uintptr_t>(source) + 5U;
    const std::int64_t distance =
        static_cast<std::int64_t>(destination) -
        static_cast<std::int64_t>(nextInstruction);
    if (distance < std::numeric_limits<std::int32_t>::min() ||
        distance > std::numeric_limits<std::int32_t>::max()) {
        error = "relative_jump_out_of_range";
        return false;
    }

    source[0] = 0xE9;
    const auto relative = static_cast<std::int32_t>(distance);
    std::memcpy(source + 1, &relative, sizeof(relative));
    return true;
}

bool InstallDetour(
    std::uint8_t* target,
    std::size_t patchLength,
    std::uintptr_t hook,
    void*& trampoline,
    std::string& error) {
    if (patchLength < 5) {
        error = "patch_too_short";
        return false;
    }

    auto* gateway = static_cast<std::uint8_t*>(VirtualAlloc(
        nullptr,
        patchLength + 5,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_EXECUTE_READWRITE));
    if (gateway == nullptr) {
        error = "trampoline_allocation_failed";
        return false;
    }
    std::memcpy(gateway, target, patchLength);
    if (!WriteRelativeJump(
            gateway + patchLength,
            reinterpret_cast<std::uintptr_t>(target + patchLength),
            error)) {
        return false;
    }

    DWORD oldProtection = 0;
    if (!VirtualProtect(
            target, patchLength, PAGE_EXECUTE_READWRITE, &oldProtection)) {
        error = "target_unprotect_failed";
        return false;
    }
    std::memset(target, 0x90, patchLength);
    const bool jumpWritten = WriteRelativeJump(target, hook, error);
    DWORD restoredProtection = 0;
    const BOOL protectionRestored = VirtualProtect(
        target, patchLength, oldProtection, &restoredProtection);
    FlushInstructionCache(GetCurrentProcess(), target, patchLength);
    if (!jumpWritten || !protectionRestored) {
        if (jumpWritten) {
            error = "target_protection_restore_failed";
        }
        return false;
    }

    trampoline = gateway;
    return true;
}

std::uint8_t* FontsData() {
    const auto address = reinterpret_cast<std::uint8_t**>(
        gModuleBase + version_142::kFontsDataRva);
    return *address;
}

int FontIndex(const void* font) {
    const auto* base = FontsData();
    const auto* value = static_cast<const std::uint8_t*>(font);
    const int count = *reinterpret_cast<int*>(
        gModuleBase + version_142::kFontsCountRva);
    if (base == nullptr || value < base) {
        return -1;
    }
    const std::size_t distance = static_cast<std::size_t>(value - base);
    if ((distance % kFontInfoExSize) != 0) {
        return -1;
    }
    const std::size_t index = distance / kFontInfoExSize;
    return index < static_cast<std::size_t>(count)
        ? static_cast<int>(index)
        : -1;
}

void* FontByIndex(int index) {
    auto* base = FontsData();
    const int count = *reinterpret_cast<int*>(
        gModuleBase + version_142::kFontsCountRva);
    if (base == nullptr || index < 0 || index >= count) {
        return nullptr;
    }
    return base + static_cast<std::size_t>(index) * kFontInfoExSize;
}

void SetActiveFont(void* self, void* font) {
    *reinterpret_cast<void**>(
        static_cast<std::uint8_t*>(self) + kActiveFontOffset) = font;
}

void* ActiveFont(void* self) {
    return *reinterpret_cast<void**>(
        static_cast<std::uint8_t*>(self) + kActiveFontOffset);
}

void* UseFont(void* self) {
    return *reinterpret_cast<void**>(
        static_cast<std::uint8_t*>(self) + kUseFontOffset);
}

void SetUseFont(void* self, void* font) {
    *reinterpret_cast<void**>(
        static_cast<std::uint8_t*>(self) + kUseFontOffset) = font;
}

float CurrentGlyphAdvance(void* self, unsigned char glyph, float scale) {
    const auto* font = static_cast<const std::uint8_t*>(UseFont(self));
    if (font == nullptr) {
        return 0.0F;
    }
    float xSkip = 0.0F;
    float glyphScale = 0.0F;
    std::memcpy(
        &xSkip,
        font + static_cast<std::size_t>(glyph) * kGlyphRecordSize + 8,
        sizeof(xSkip));
    std::memcpy(
        &glyphScale, font + kGlyphScaleOffset, sizeof(glyphScale));
    return xSkip * glyphScale * scale;
}

bool IsEncodedPair(const unsigned char* text) {
    return text[0] >= kLeadStart && text[0] <= kLeadEnd &&
           text[1] >= kTrailStart && text[1] <= kTrailEnd;
}

void __fastcall HookSetupFonts(void* self, void*) {
    gOriginalSetupFonts(self);
    int loaded = 0;
    for (std::size_t page = 0; page < kPageCount; ++page) {
        std::array<char, 32> name{};
        sprintf_s(name.data(), name.size(), "fonts/q4cn_p%02u",
                  static_cast<unsigned int>(page));
        const int index = gFindFont(self, name.data());
        gPageFontIndexes[page] = index;
        if (index >= 0) {
            ++loaded;
        }
    }
    AppendRuntimeLog(
        "font_pages=" + std::to_string(loaded) + "/" +
        std::to_string(kPageCount));
}

int __fastcall HookDrawText(
    void* self,
    void*,
    float x,
    float y,
    float scale,
    Vec4 color,
    const char* text,
    float adjust,
    int limit,
    int style,
    int cursor,
    int ravenFlag) {
    if (text == nullptr) {
        return gOriginalDrawText(
            self, x, y, scale, color, text, adjust, limit, style, cursor,
            ravenFlag);
    }

    const auto* bytes = reinterpret_cast<const unsigned char*>(text);
    bool containsEncodedPair = false;
    for (std::size_t index = 0; bytes[index] != 0; ++index) {
        if (IsEncodedPair(bytes + index)) {
            containsEncodedPair = true;
            break;
        }
    }
    if (!containsEncodedPair) {
        return gOriginalDrawText(
            self, x, y, scale, color, text, adjust, limit, style, cursor,
            ravenFlag);
    }

    void* originalActiveFont = ActiveFont(self);
    void* originalUseFont = UseFont(self);
    const int originalFontIndex = FontIndex(originalActiveFont);
    int count = 0;
    int byteIndex = 0;

    while (bytes[byteIndex] != 0 &&
           (limit <= 0 || byteIndex < limit)) {
        if (IsEncodedPair(bytes + byteIndex) &&
            (limit <= 0 || byteIndex + 1 < limit)) {
            const std::size_t page =
                static_cast<std::size_t>(bytes[byteIndex] - kLeadStart);
            void* pageFont = FontByIndex(gPageFontIndexes[page]);
            if (pageFont != nullptr) {
                SetActiveFont(self, pageFont);
                const char glyphText[2] = {
                    static_cast<char>(bytes[byteIndex + 1]), '\0'};
                gOriginalDrawText(
                    self,
                    x,
                    y,
                    scale,
                    color,
                    glyphText,
                    adjust,
                    0,
                    style,
                    -1,
                    ravenFlag);
                x += CurrentGlyphAdvance(
                         self, bytes[byteIndex + 1], scale) +
                     adjust;
                count += 2;
                byteIndex += 2;
                continue;
            }
        }

        const int runStart = byteIndex;
        while (bytes[byteIndex] != 0 &&
               (limit <= 0 || byteIndex < limit) &&
               !IsEncodedPair(bytes + byteIndex)) {
            ++byteIndex;
        }
        const std::string run(
            text + runStart,
            text + byteIndex);
        if (void* font = FontByIndex(originalFontIndex)) {
            SetActiveFont(self, font);
        }
        const int localCursor =
            cursor >= runStart && cursor <= byteIndex
                ? cursor - runStart
                : -1;
        count += gOriginalDrawText(
            self,
            x,
            y,
            scale,
            color,
            run.c_str(),
            adjust,
            0,
            style,
            localCursor,
            ravenFlag);
        for (const unsigned char glyph : run) {
            x += CurrentGlyphAdvance(self, glyph, scale) + adjust;
        }
    }

    if (void* font = FontByIndex(originalFontIndex)) {
        SetActiveFont(self, font);
    } else {
        SetActiveFont(self, originalActiveFont);
    }
    SetUseFont(self, originalUseFont);
    return count;
}

}  // namespace

void SetRuntimeLogPath(const std::filesystem::path& path) {
    gLogPath = path;
}

bool InstallRuntimeHooks(std::uint8_t* moduleBase, std::ostream& log) {
    gModuleBase = moduleBase;
    gPageFontIndexes.fill(-1);
    gFindFont = FunctionFromAddress<FindFontFunction>(
        moduleBase + version_142::kFindFontRva);

    void* setupTrampoline = nullptr;
    std::string error;
    const auto setupHook = FunctionAddress(&HookSetupFonts);
    if (!InstallDetour(
            moduleBase + version_142::kSetupFontsRva,
            8,
            setupHook,
            setupTrampoline,
            error)) {
        log << "hook=SetupFonts:failed:" << error << '\n';
        return false;
    }
    gOriginalSetupFonts =
        FunctionFromAddress<SetupFontsFunction>(setupTrampoline);
    log << "hook=SetupFonts:ok\n";

    void* drawTextTrampoline = nullptr;
    const auto drawTextHook = FunctionAddress(&HookDrawText);
    if (!InstallDetour(
            moduleBase + version_142::kDrawTextRva,
            10,
            drawTextHook,
            drawTextTrampoline,
            error)) {
        log << "hook=DrawText:failed:" << error << '\n';
        return false;
    }
    gOriginalDrawText =
        FunctionFromAddress<DrawTextFunction>(drawTextTrampoline);
    log << "hook=DrawText:ok\n";
    return true;
}

}  // namespace q4cn
