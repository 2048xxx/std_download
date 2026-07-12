@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title ZKBZ 标准PDF下载

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY where python >nul 2>&1 && set "PY=python"

if not defined PY (
    echo.
    echo  [错误] 未找到 Python 3
    echo  请安装 Python 并勾选 "Add to PATH"
    echo.
    pause
    exit /b 1
)

echo.
echo  正在释放 5000 端口，如有旧进程会先结束…
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5000" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo  检查运行依赖…
%PY% -c "import flask, pymysql" >nul 2>&1
if errorlevel 1 (
    echo  首次或缺包，正在安装 requirements.txt …
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo  [错误] 依赖安装失败，请检查网络或 Python 环境
        pause
        exit /b 1
    )
)

if not exist "data\standards.db" (
    echo  [提示] 未找到 data\standards.db，标准检索可能不可用
    echo         可运行: python scripts\seed_demo_index.py
)
if not exist "data\terms.db" (
    echo  [提示] 未找到 data\terms.db，术语检索可能不可用
    echo         可运行: python scripts\seed_demo_index.py
)
if not exist "data\units.db" (
    echo  [提示] 未找到 data\units.db，省/市/起草单位筛选可能不可用
    echo         需要时可运行: python scripts\build_unit_index.py
)

echo.
echo  ========================================
echo    ZKBZ 标准PDF下载
echo    地址: http://127.0.0.1:5000/
echo    启动后会自动打开浏览器
echo    请勿关闭本窗口 - 关闭即停止服务
echo  ========================================
echo.

%PY% backend\run.py
set "EC=%ERRORLEVEL%"

if not "%EC%"=="0" (
    echo.
    echo  [启动失败] 错误代码 %EC%
    echo  请把上面报错信息截图发维护人员
    echo.
    pause
    exit /b %EC%
)

pause
endlocal
