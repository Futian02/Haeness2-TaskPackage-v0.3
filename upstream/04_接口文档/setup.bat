@echo off
rem 本脚本将四个参考代码仓库浅克隆到运行时当前目录的 reference_code\ 下。
rem 运行前请先安装 Git，并确保命令行能执行 git；每个仓库使用 --depth 1 节省体积。
rem 已存在的目标路径会跳过，单个仓库克隆失败后继续处理其余仓库。
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul

where git.exe >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Git，请先安装 Git 并将其加入 PATH。
    exit /b 1
)

set "TARGET_ROOT=%CD%\reference_code"
if not exist "%TARGET_ROOT%\" (
    mkdir "%TARGET_ROOT%"
    if errorlevel 1 (
        echo [错误] 无法创建目录："%TARGET_ROOT%"
        exit /b 1
    )
)

set /a SUCCESS_COUNT=0, SKIPPED_COUNT=0, FAILED_COUNT=0 >nul
set "SUCCESS_LIST="
set "SKIPPED_LIST="
set "FAILED_LIST="

call :clone_repo "Qwen-Agent" "https://github.com/QwenLM/Qwen-Agent"
call :clone_repo "gorilla" "https://github.com/ShishirPatil/gorilla"
call :clone_repo "LLaMA-Factory" "https://github.com/hiyouga/LLaMA-Factory"
call :clone_repo "ToolAlpaca" "https://github.com/tangqiaoyu/ToolAlpaca"

if not defined SUCCESS_LIST set "SUCCESS_LIST=无"
if not defined SKIPPED_LIST set "SKIPPED_LIST=无"
if not defined FAILED_LIST set "FAILED_LIST=无"
echo.
echo ========== 下载汇总 ==========
echo 成功（%SUCCESS_COUNT%）：%SUCCESS_LIST%
echo 跳过（%SKIPPED_COUNT%）：%SKIPPED_LIST%
echo 失败（%FAILED_COUNT%）：%FAILED_LIST%
echo.
echo 提示：数据集文件很大，需要按各仓库 README 单独下载。

if %FAILED_COUNT% GTR 0 exit /b 1
exit /b 0

:clone_repo
set "REPO_NAME=%~1"
set "REPO_URL=%~2"
set "REPO_DIR=%TARGET_ROOT%\%~1"

if exist "%REPO_DIR%" (
    echo [跳过] %REPO_NAME%：目标路径已存在（"%REPO_DIR%"）。
    set /a SKIPPED_COUNT+=1 >nul
    set "SKIPPED_LIST=%SKIPPED_LIST% %REPO_NAME%"
    exit /b 0
)

echo.
echo [开始] %REPO_NAME%
git.exe clone --depth 1 "%REPO_URL%" "%REPO_DIR%"
if errorlevel 1 (
    echo [失败] %REPO_NAME%：继续处理下一个仓库。
    set /a FAILED_COUNT+=1 >nul
    set "FAILED_LIST=%FAILED_LIST% %REPO_NAME%"
) else (
    echo [成功] %REPO_NAME%
    set /a SUCCESS_COUNT+=1 >nul
    set "SUCCESS_LIST=%SUCCESS_LIST% %REPO_NAME%"
)
exit /b 0
