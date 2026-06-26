#define UNICODE
#define _UNICODE

#include <windows.h>
#include <shellapi.h>
#include <wchar.h>

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous_instance, PWSTR command_line, int show_command)
{
    wchar_t launcher_path[MAX_PATH];
    wchar_t app_dir[MAX_PATH];
    wchar_t target_path[MAX_PATH];
    wchar_t *last_separator;
    SHELLEXECUTEINFOW execute_info;

    (void)instance;
    (void)previous_instance;
    (void)command_line;

    if (GetModuleFileNameW(NULL, launcher_path, MAX_PATH) == 0) {
        MessageBoxW(NULL, L"无法定位启动器路径。", L"cEmoji", MB_ICONERROR | MB_OK);
        return 1;
    }

    last_separator = wcsrchr(launcher_path, L'\\');
    if (last_separator == NULL) {
        MessageBoxW(NULL, L"无法解析启动目录。", L"cEmoji", MB_ICONERROR | MB_OK);
        return 1;
    }
    *last_separator = L'\0';

    if (lstrlenW(launcher_path) + lstrlenW(L"\\app") >= MAX_PATH) {
        MessageBoxW(NULL, L"安装路径过长。", L"cEmoji", MB_ICONERROR | MB_OK);
        return 1;
    }

    lstrcpyW(app_dir, launcher_path);
    lstrcatW(app_dir, L"\\app");

    if (lstrlenW(app_dir) + lstrlenW(L"\\cEmoji.exe") >= MAX_PATH) {
        MessageBoxW(NULL, L"应用路径过长。", L"cEmoji", MB_ICONERROR | MB_OK);
        return 1;
    }

    lstrcpyW(target_path, app_dir);
    lstrcatW(target_path, L"\\cEmoji.exe");

    ZeroMemory(&execute_info, sizeof(execute_info));
    execute_info.cbSize = sizeof(execute_info);
    execute_info.lpVerb = L"open";
    execute_info.lpFile = target_path;
    execute_info.lpDirectory = app_dir;
    execute_info.nShow = show_command;

    if (!ShellExecuteExW(&execute_info)) {
        MessageBoxW(NULL, L"无法启动 app\\cEmoji.exe。", L"cEmoji", MB_ICONERROR | MB_OK);
        return 1;
    }

    return 0;
}