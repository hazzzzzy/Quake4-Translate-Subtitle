#include <windows.h>
#include <shellapi.h>
#include <shobjidl.h>

#include <filesystem>
#include <string>
#include <system_error>
#include <vector>

namespace fs = std::filesystem;

namespace {

constexpr wchar_t kProductName[] = L"Quake 4 简体中文汉化";
constexpr wchar_t kInstallDirectory[] = L"Quake4-Chinese";
// 同一二进制按自身文件名分流：含"英文"= 英文原版+英文字幕模式
// （安装器将本 EXE 复制为 Quake4中文启动器.exe / Quake4英文字幕启动器.exe）
constexpr wchar_t kEnglishMarker[] = L"英文";
constexpr wchar_t kEnglishSaveDirectory[] = L"savedata-english";

bool IsEnglishMode(const fs::path& launcherPath) {
    return launcherPath.filename().wstring().find(kEnglishMarker) !=
           std::wstring::npos;
}

void ShowError(const std::wstring& message) {
    MessageBoxW(nullptr, message.c_str(), kProductName, MB_OK | MB_ICONERROR);
}

fs::path ExecutablePath() {
    std::vector<wchar_t> buffer(32768);
    const DWORD length = GetModuleFileNameW(
        nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (length == 0 || length >= buffer.size()) {
        return {};
    }
    return fs::path(std::wstring(buffer.data(), length));
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
    const fs::path& engine,
    const fs::path& gameDirectory,
    const fs::path& saveDirectory,
    bool englishMode) {
    // 英文模式：原版界面/字体原样，仅开字幕；宽字符 GUI 仅中文需要
    const std::vector<std::wstring> arguments = {
        engine.wstring(),
        L"+set", L"fs_basepath", gameDirectory.wstring(),
        L"+set", L"fs_savepath", saveDirectory.wstring(),
        L"+set", L"sys_lang", englishMode ? L"english" : L"chinese",
        L"+set", L"harm_gui_wideCharLang", englishMode ? L"0" : L"1",
        L"+set", L"gui_smallFontLimit", L"0",
        L"+set", L"image_forceDownSize", L"0",
        L"+set", L"harm_g_subtitles", L"1",
        L"+set", L"com_allowConsole", L"1",
        L"+set", L"logFile", L"2",
        L"+set", L"r_fullscreen", L"1",
        L"+set", L"r_mode", L"-1",
        L"+set", L"r_customWidth", L"1920",
        L"+set", L"r_customHeight", L"1080",
        L"+set", L"r_useShadowMapping", L"1",
        L"+set", L"harm_r_softStencilShadow", L"0",
    };

    std::wstring commandLine;
    for (const auto& argument : arguments) {
        if (!commandLine.empty()) {
            commandLine.push_back(L' ');
        }
        commandLine += QuoteArgument(argument);
    }
    return commandLine;
}

HRESULT CreateDesktopShortcut(
    const fs::path& shortcutPath,
    const fs::path& launcherPath) {
    const HRESULT initializeResult = CoInitializeEx(
        nullptr, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE);
    const bool shouldUninitialize = SUCCEEDED(initializeResult);
    if (FAILED(initializeResult) && initializeResult != RPC_E_CHANGED_MODE) {
        return initializeResult;
    }

    IShellLinkW* shellLink = nullptr;
    HRESULT result = CoCreateInstance(
        CLSID_ShellLink,
        nullptr,
        CLSCTX_INPROC_SERVER,
        IID_IShellLinkW,
        reinterpret_cast<void**>(&shellLink));
    if (SUCCEEDED(result)) {
        result = shellLink->SetPath(launcherPath.c_str());
    }
    if (SUCCEEDED(result)) {
        result = shellLink->SetWorkingDirectory(
            launcherPath.parent_path().c_str());
    }
    if (SUCCEEDED(result)) {
        result = shellLink->SetDescription(kProductName);
    }
    if (SUCCEEDED(result)) {
        result = shellLink->SetIconLocation(launcherPath.c_str(), 0);
    }

    IPersistFile* persistFile = nullptr;
    if (SUCCEEDED(result)) {
        result = shellLink->QueryInterface(
            IID_IPersistFile, reinterpret_cast<void**>(&persistFile));
    }
    if (SUCCEEDED(result)) {
        result = persistFile->Save(shortcutPath.c_str(), TRUE);
    }

    if (persistFile != nullptr) {
        persistFile->Release();
    }
    if (shellLink != nullptr) {
        shellLink->Release();
    }
    if (shouldUninitialize) {
        CoUninitialize();
    }
    return result;
}

int LaunchGame(const fs::path& launcherPath) {
    const bool englishMode = IsEnglishMode(launcherPath);
    const fs::path gameDirectory = launcherPath.parent_path();
    const fs::path installDirectory = gameDirectory / kInstallDirectory;
    const fs::path engineDirectory = installDirectory / L"engine";
    const fs::path engine = engineDirectory / L"Quake4.exe";
    const fs::path gameModule = engineDirectory / L"q4game.dll";
    const fs::path saveDirectory =
        installDirectory / (englishMode ? kEnglishSaveDirectory : L"savedata");

    const std::vector<fs::path> requiredFiles = {
        gameDirectory / L"q4base" / L"pak001.pk4",
        gameDirectory / L"q4base" / L"pak014.pk4",
        gameDirectory / L"q4base" / L"pak021.pk4",
        gameDirectory / L"q4base" / L"zpak_english.pk4",
        engine,
        gameModule,
    };
    std::error_code error;
    for (const auto& path : requiredFiles) {
        if (!fs::is_regular_file(path, error)) {
            ShowError(L"安装文件不完整：\n" + path.wstring() +
                      L"\n\n请重新运行汉化安装器。");
            return 2;
        }
    }

    fs::create_directories(saveDirectory / L"q4base", error);
    if (error) {
        ShowError(L"建立汉化版存档目录失败：\n" + saveDirectory.wstring());
        return 3;
    }

    std::wstring commandLine =
        BuildCommandLine(engine, gameDirectory, saveDirectory, englishMode);
    STARTUPINFOW startupInfo{};
    startupInfo.cb = sizeof(startupInfo);
    PROCESS_INFORMATION processInfo{};
    const BOOL started = CreateProcessW(
        engine.c_str(),
        commandLine.data(),
        nullptr,
        nullptr,
        FALSE,
        0,
        nullptr,
        engineDirectory.c_str(),
        &startupInfo,
        &processInfo);
    if (!started) {
        ShowError(L"启动汉化版失败，系统错误码：" +
                  std::to_wstring(GetLastError()));
        return 4;
    }

    CloseHandle(processInfo.hThread);
    CloseHandle(processInfo.hProcess);
    return 0;
}

}  // namespace

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    const fs::path launcherPath = ExecutablePath();
    if (launcherPath.empty()) {
        ShowError(L"读取启动器路径失败。");
        return 1;
    }

    int argumentCount = 0;
    wchar_t** arguments = CommandLineToArgvW(GetCommandLineW(), &argumentCount);
    if (arguments != nullptr && argumentCount == 3 &&
        std::wstring(arguments[1]) == L"--create-shortcut") {
        const fs::path shortcutPath = arguments[2];
        const HRESULT result = CreateDesktopShortcut(shortcutPath, launcherPath);
        LocalFree(arguments);
        return SUCCEEDED(result) ? 0 : 5;
    }
    if (arguments != nullptr) {
        LocalFree(arguments);
    }
    return LaunchGame(launcherPath);
}
