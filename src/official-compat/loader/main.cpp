#include <windows.h>
#include <bcrypt.h>

#include <array>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <string>
#include <vector>

#include "version_142.h"

namespace fs = std::filesystem;

namespace {

struct Options {
    fs::path gameDir;
    fs::path saveDir;
    bool verifyOnly = false;
    std::vector<std::wstring> extraArguments;
};

void PrintUsage() {
    std::wcerr
        << L"Usage: Q4CNLoader.exe --game-dir <path> --save-dir <path> "
        << L"[--verify-only] [-- <extra Quake4 arguments>]\n";
}

bool ParseOptions(int argc, wchar_t** argv, Options& options) {
    for (int index = 1; index < argc; ++index) {
        const std::wstring argument = argv[index];
        if (argument == L"--") {
            for (++index; index < argc; ++index) {
                options.extraArguments.emplace_back(argv[index]);
            }
            break;
        }
        if (argument == L"--game-dir" && index + 1 < argc) {
            options.gameDir = argv[++index];
            continue;
        }
        if (argument == L"--save-dir" && index + 1 < argc) {
            options.saveDir = argv[++index];
            continue;
        }
        if (argument == L"--verify-only") {
            options.verifyOnly = true;
            continue;
        }
        std::wcerr << L"Unknown argument: " << argument << L"\n";
        return false;
    }
    return !options.gameDir.empty() && !options.saveDir.empty();
}

bool HashFileSha256(
    const fs::path& path,
    std::array<std::uint8_t, 32>& digest,
    std::wstring& error) {
    BCRYPT_ALG_HANDLE algorithm = nullptr;
    BCRYPT_HASH_HANDLE hash = nullptr;
    HANDLE file = INVALID_HANDLE_VALUE;
    std::vector<std::uint8_t> hashObject;
    bool success = false;

    do {
        if (BCryptOpenAlgorithmProvider(
                &algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0) {
            error = L"BCryptOpenAlgorithmProvider failed";
            break;
        }

        DWORD objectSize = 0;
        DWORD resultSize = 0;
        if (BCryptGetProperty(
                algorithm,
                BCRYPT_OBJECT_LENGTH,
                reinterpret_cast<PUCHAR>(&objectSize),
                sizeof(objectSize),
                &resultSize,
                0) < 0) {
            error = L"BCryptGetProperty failed";
            break;
        }

        hashObject.resize(objectSize);
        if (BCryptCreateHash(
                algorithm,
                &hash,
                hashObject.data(),
                static_cast<ULONG>(hashObject.size()),
                nullptr,
                0,
                0) < 0) {
            error = L"BCryptCreateHash failed";
            break;
        }

        file = CreateFileW(
            path.c_str(),
            GENERIC_READ,
            FILE_SHARE_READ,
            nullptr,
            OPEN_EXISTING,
            FILE_FLAG_SEQUENTIAL_SCAN,
            nullptr);
        if (file == INVALID_HANDLE_VALUE) {
            error = L"CreateFileW failed: " + std::to_wstring(GetLastError());
            break;
        }

        std::array<std::uint8_t, 64 * 1024> buffer{};
        for (;;) {
            DWORD bytesRead = 0;
            if (!ReadFile(
                    file,
                    buffer.data(),
                    static_cast<DWORD>(buffer.size()),
                    &bytesRead,
                    nullptr)) {
                error = L"ReadFile failed: " + std::to_wstring(GetLastError());
                break;
            }
            if (bytesRead == 0) {
                if (BCryptFinishHash(
                        hash,
                        digest.data(),
                        static_cast<ULONG>(digest.size()),
                        0) < 0) {
                    error = L"BCryptFinishHash failed";
                    break;
                }
                success = true;
                break;
            }
            if (BCryptHashData(hash, buffer.data(), bytesRead, 0) < 0) {
                error = L"BCryptHashData failed";
                break;
            }
        }
    } while (false);

    if (file != INVALID_HANDLE_VALUE) {
        CloseHandle(file);
    }
    if (hash != nullptr) {
        BCryptDestroyHash(hash);
    }
    if (algorithm != nullptr) {
        BCryptCloseAlgorithmProvider(algorithm, 0);
    }
    return success;
}

std::wstring QuoteArgument(const std::wstring& value) {
    if (value.find_first_of(L" \t\"") == std::wstring::npos) {
        return value;
    }

    std::wstring quoted = L"\"";
    std::size_t backslashes = 0;
    for (const wchar_t ch : value) {
        if (ch == L'\\') {
            ++backslashes;
            continue;
        }
        if (ch == L'\"') {
            quoted.append(backslashes * 2 + 1, L'\\');
            quoted.push_back(ch);
            backslashes = 0;
            continue;
        }
        quoted.append(backslashes, L'\\');
        backslashes = 0;
        quoted.push_back(ch);
    }
    quoted.append(backslashes * 2, L'\\');
    quoted.push_back(L'\"');
    return quoted;
}

std::wstring BuildCommandLine(
    const fs::path& executable,
    const Options& options) {
    std::vector<std::wstring> arguments = {
        executable.wstring(),
        L"+set", L"fs_basepath", options.gameDir.wstring(),
        L"+set", L"fs_savepath", options.saveDir.wstring(),
        L"+set", L"sys_lang", L"chinese",
        L"+set", L"gui_smallFontLimit", L"0",
        L"+set", L"image_forceDownSize", L"0",
        L"+set", L"com_allowConsole", L"1",
        L"+set", L"logFile", L"2",
        L"+set", L"r_fullscreen", L"0",
        L"+set", L"r_mode", L"3",
    };
    arguments.insert(
        arguments.end(),
        options.extraArguments.begin(),
        options.extraArguments.end());

    std::wstring commandLine;
    for (const auto& argument : arguments) {
        if (!commandLine.empty()) {
            commandLine.push_back(L' ');
        }
        commandLine += QuoteArgument(argument);
    }
    return commandLine;
}

bool InjectLibrary(
    HANDLE process,
    const fs::path& library,
    std::wstring& error) {
    const std::wstring libraryPath = library.wstring();
    const SIZE_T bytes = (libraryPath.size() + 1) * sizeof(wchar_t);
    void* remoteBuffer = VirtualAllocEx(
        process, nullptr, bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (remoteBuffer == nullptr) {
        error = L"VirtualAllocEx failed: " + std::to_wstring(GetLastError());
        return false;
    }

    bool success = false;
    HANDLE remoteThread = nullptr;
    do {
        if (!WriteProcessMemory(
                process,
                remoteBuffer,
                libraryPath.c_str(),
                bytes,
                nullptr)) {
            error = L"WriteProcessMemory failed: " +
                    std::to_wstring(GetLastError());
            break;
        }

        const HMODULE kernel32 = GetModuleHandleW(L"kernel32.dll");
        const auto loadLibrary = reinterpret_cast<LPTHREAD_START_ROUTINE>(
            GetProcAddress(kernel32, "LoadLibraryW"));
        if (loadLibrary == nullptr) {
            error = L"GetProcAddress(LoadLibraryW) failed";
            break;
        }

        remoteThread = CreateRemoteThread(
            process,
            nullptr,
            0,
            loadLibrary,
            remoteBuffer,
            0,
            nullptr);
        if (remoteThread == nullptr) {
            error = L"CreateRemoteThread failed: " +
                    std::to_wstring(GetLastError());
            break;
        }

        if (WaitForSingleObject(remoteThread, 15000) != WAIT_OBJECT_0) {
            error = L"LoadLibraryW remote thread timed out";
            break;
        }

        DWORD remoteModule = 0;
        if (!GetExitCodeThread(remoteThread, &remoteModule) || remoteModule == 0) {
            error = L"LoadLibraryW failed in target process";
            break;
        }
        success = true;
    } while (false);

    if (remoteThread != nullptr) {
        CloseHandle(remoteThread);
    }
    VirtualFreeEx(process, remoteBuffer, 0, MEM_RELEASE);
    return success;
}

fs::path CurrentExecutableDirectory() {
    std::vector<wchar_t> buffer(32768);
    const DWORD length = GetModuleFileNameW(
        nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (length == 0 ||
        static_cast<std::size_t>(length) >= buffer.size()) {
        return {};
    }
    return fs::path(std::wstring(buffer.data(), length)).parent_path();
}

}  // namespace

int wmain(int argc, wchar_t** argv) {
    Options options;
    if (!ParseOptions(argc, argv, options)) {
        PrintUsage();
        return 2;
    }

    std::error_code fsError;
    options.gameDir = fs::weakly_canonical(options.gameDir, fsError);
    if (fsError) {
        std::wcerr << L"Invalid game directory, error=" << fsError.value()
                   << L"\n";
        return 3;
    }
    options.saveDir = fs::absolute(options.saveDir, fsError);
    if (fsError) {
        std::wcerr << L"Invalid save directory\n";
        return 3;
    }

    const fs::path gameExe =
        options.gameDir / q4cn::version_142::kExecutableName;
    const fs::path pak021 = options.gameDir / L"q4base" / L"pak021.pk4";
    if (!fs::is_regular_file(gameExe) || !fs::is_regular_file(pak021)) {
        std::wcerr << L"Quake 4 1.4.2 files were not found in: "
                   << options.gameDir << L"\n";
        return 4;
    }

    std::array<std::uint8_t, 32> digest{};
    std::wstring hashError;
    if (!HashFileSha256(gameExe, digest, hashError)) {
        std::wcerr << hashError << L"\n";
        return 5;
    }
    if (digest != q4cn::version_142::kSha256) {
        std::wcerr << L"Quake4.exe SHA-256 is not the supported 1.4.2 build\n";
        return 6;
    }

    std::wcout << L"Official Quake4.exe 1.4.2 verified\n";
    if (options.verifyOnly) {
        return 0;
    }

    fs::create_directories(options.saveDir / L"q4base", fsError);
    if (fsError) {
        std::wcerr << L"Create save directory failed, error="
                   << fsError.value() << L"\n";
        return 7;
    }

    const fs::path compatDll =
        CurrentExecutableDirectory() / L"Q4CNCompat32.dll";
    if (!fs::is_regular_file(compatDll)) {
        std::wcerr << L"Missing compatibility DLL: " << compatDll << L"\n";
        return 8;
    }

    const std::wstring readyEventName =
        L"Local\\Q4CNCompatReady-" + std::to_wstring(GetCurrentProcessId()) +
        L"-" + std::to_wstring(GetTickCount64());
    HANDLE readyEvent = CreateEventW(
        nullptr, TRUE, FALSE, readyEventName.c_str());
    if (readyEvent == nullptr) {
        std::wcerr << L"CreateEventW failed: " << GetLastError() << L"\n";
        return 9;
    }

    const fs::path compatLog = options.saveDir / L"q4base" / L"q4cn-compat.log";
    SetEnvironmentVariableW(L"Q4CN_COMPAT_READY_EVENT", readyEventName.c_str());
    SetEnvironmentVariableW(L"Q4CN_COMPAT_LOG", compatLog.c_str());

    std::wstring commandLine = BuildCommandLine(gameExe, options);
    STARTUPINFOW startupInfo{};
    startupInfo.cb = sizeof(startupInfo);
    PROCESS_INFORMATION processInfo{};
    std::array<wchar_t, 32768> previousCompatLayer{};
    const DWORD previousCompatLayerLength = GetEnvironmentVariableW(
        L"__COMPAT_LAYER",
        previousCompatLayer.data(),
        static_cast<DWORD>(previousCompatLayer.size()));
    SetEnvironmentVariableW(L"__COMPAT_LAYER", L"RunAsInvoker");
    const BOOL processCreated = CreateProcessW(
            gameExe.c_str(),
            commandLine.data(),
            nullptr,
            nullptr,
            FALSE,
            CREATE_SUSPENDED,
            nullptr,
            options.gameDir.c_str(),
            &startupInfo,
            &processInfo);
    const DWORD createProcessError =
        processCreated ? ERROR_SUCCESS : GetLastError();
    if (previousCompatLayerLength > 0 &&
        static_cast<std::size_t>(previousCompatLayerLength) <
            previousCompatLayer.size()) {
        SetEnvironmentVariableW(
            L"__COMPAT_LAYER", previousCompatLayer.data());
    } else {
        SetEnvironmentVariableW(L"__COMPAT_LAYER", nullptr);
    }
    if (!processCreated) {
        std::wcerr << L"CreateProcessW failed: " << createProcessError
                   << L"\n";
        CloseHandle(readyEvent);
        return 10;
    }

    std::wstring injectError;
    bool started = InjectLibrary(processInfo.hProcess, compatDll, injectError);
    if (started) {
        started = WaitForSingleObject(readyEvent, 10000) == WAIT_OBJECT_0;
        if (!started) {
            injectError = L"Compatibility DLL signature verification timed out";
        }
    }

    if (!started) {
        std::wcerr << injectError << L"\n";
        TerminateProcess(processInfo.hProcess, 11);
        WaitForSingleObject(processInfo.hProcess, 5000);
        CloseHandle(processInfo.hThread);
        CloseHandle(processInfo.hProcess);
        CloseHandle(readyEvent);
        return 11;
    }

    if (ResumeThread(processInfo.hThread) == static_cast<DWORD>(-1)) {
        std::wcerr << L"ResumeThread failed: " << GetLastError() << L"\n";
        TerminateProcess(processInfo.hProcess, 12);
        CloseHandle(processInfo.hThread);
        CloseHandle(processInfo.hProcess);
        CloseHandle(readyEvent);
        return 12;
    }

    std::wcout << L"Quake4.exe started, pid=" << processInfo.dwProcessId << L"\n";
    CloseHandle(processInfo.hThread);
    CloseHandle(processInfo.hProcess);
    CloseHandle(readyEvent);
    return 0;
}
