@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title CraftTune - Minecraft 模组参数工坊

set "PY=python"
where python >nul 2>nul
if errorlevel 1 (
  where py >nul 2>nul
  if errorlevel 1 (
    echo.
    echo  [错误] 没有找到 Python。
    echo  请安装 Python 3.8 或更高版本，或直接运行已打包的 CraftTune.exe。
    echo.
    pause
    exit /b 1
  )
  set "PY=py -3"
)

%PY% -c "import PyQt5, toml, PIL, minecraft_launcher_lib" >nul 2>nul
if errorlevel 1 (
  echo.
  echo  正在安装桌面界面所需的 Python 组件...
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo  [错误] 依赖安装失败，请检查网络，或手动执行：
    echo         %PY% -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
  )
)

echo.
echo  正在启动 CraftTune 原生桌面版...
echo  关闭程序窗口即可退出。
echo.
%PY% desktop.py
if errorlevel 1 (
  echo.
  echo  程序已退出，出现错误。请把上面的提示截图反馈。
  pause
)
endlocal
