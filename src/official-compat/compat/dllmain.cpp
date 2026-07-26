#include <windows.h>

#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>

#include "runtime_hooks.h"
#include "version_142.h"

namespace fs = std::filesystem;

namespace {

fs::path ReadEnvironmentPath(const wchar_t* name) {
    const DWORD required = GetEnvironmentVariableW(name, nullptr, 0);
    if (required == 0) {
        return {};
    }
    std::wstring value(required, L'\0');
    const DWORD length = GetEnvironmentVariableW(
        name, value.data(), static_cast<DWORD>(value.size()));
    if (length == 0 || length >= value.size()) {
        return {};
    }
    value.resize(length);
    return fs::path(value);
}

bool SignalReady() {
    wchar_t eventName[256]{};
    const DWORD length = GetEnvironmentVariableW(
        L"Q4CN_COMPAT_READY_EVENT", eventName, _countof(eventName));
    if (length == 0 || length >= _countof(eventName)) {
        return false;
    }
    HANDLE event = OpenEventW(EVENT_MODIFY_STATE, FALSE, eventName);
    if (event == nullptr) {
        return false;
    }
    const bool success = SetEvent(event) != FALSE;
    CloseHandle(event);
    return success;
}

DWORD WINAPI VerifyOfficialExecutable(void*) {
    const fs::path logPath = ReadEnvironmentPath(L"Q4CN_COMPAT_LOG");
    q4cn::SetRuntimeLogPath(logPath);
    std::ofstream log;
    if (!logPath.empty()) {
        log.open(logPath, std::ios::out | std::ios::trunc);
    }

    const auto base = reinterpret_cast<std::uint8_t*>(GetModuleHandleW(nullptr));
    if (base == nullptr) {
        if (log) {
            log << "status=module_not_found\n";
        }
        return 1;
    }

    const auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) {
        if (log) {
            log << "status=invalid_dos_header\n";
        }
        return 2;
    }

    const auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS32*>(
        base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE ||
        nt->FileHeader.Machine != IMAGE_FILE_MACHINE_I386 ||
        nt->FileHeader.TimeDateStamp != q4cn::version_142::kPeTimestamp ||
        nt->OptionalHeader.SizeOfImage != q4cn::version_142::kImageSize) {
        if (log) {
            log << "status=unsupported_pe\n";
        }
        return 3;
    }

    for (const auto& signature : q4cn::version_142::kFunctionSignatures) {
        const auto* address = base + signature.rva;
        if (std::memcmp(
                address, signature.bytes.data(), signature.bytes.size()) != 0) {
            if (log) {
                log << "status=signature_mismatch\n";
                log << "function=" << signature.name << "\n";
            }
            return 4;
        }
        if (log) {
            log << "signature=" << signature.name << ":ok\n";
        }
    }

    if (!q4cn::InstallRuntimeHooks(base, log)) {
        if (log) {
            log << "status=hook_install_failed\n";
        }
        return 5;
    }

    if (log) {
        log << "status=ready\n";
        log.flush();
    }
    return SignalReady() ? 0 : 6;
}

}  // namespace

extern "C" __declspec(dllexport) DWORD WINAPI Q4CN_GetCompatVersion() {
    return 1;
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID) {
    if (reason != DLL_PROCESS_ATTACH) {
        return TRUE;
    }
    DisableThreadLibraryCalls(module);
    HANDLE worker = CreateThread(
        nullptr, 0, VerifyOfficialExecutable, nullptr, 0, nullptr);
    if (worker == nullptr) {
        return FALSE;
    }
    CloseHandle(worker);
    return TRUE;
}
