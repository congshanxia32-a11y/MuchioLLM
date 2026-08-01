@echo off
cd /d %~dp0
rem NOTE: This file is Shift-JIS (CP932) encoded ON PURPOSE. Do NOT save as UTF-8.
rem cmd on Japanese Windows parses CP932 natively; UTF-8 Japanese breaks parsing.
rem Flow uses goto (no parenthesized blocks) - keep it that way.
echo ==== MuchioLLM setup ====
echo.

where python >nul 2>&1
if not errorlevel 1 goto :havepython
echo [NG] Python が見つかりません。
echo      https://www.python.org/ から Python 3.10 以上をインストールして、
echo      インストーラの「Add python.exe to PATH」に必ずチェックを入れてください。
pause
exit /b 1

:havepython
echo [1/4] 必須ライブラリを入れます...
python -m pip install -r requirements.txt
if not errorlevel 1 goto :pipok
echo [NG] pip install に失敗しました。ネット接続を確認してもう一度実行してください。
pause
exit /b 1

:pipok
echo.
choice /C YN /M "[2/4] 声紋識別・だれの声か判定 も入れますか? torch込みで数GBあります"
if not errorlevel 2 python -m pip install speechbrain torch

echo.
choice /C YN /M "[3/4] GPU音声認識・NVIDIA GPUがある人向け も入れますか?"
if not errorlevel 2 python -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12

echo.
echo [4/4] Ollama を確認します...
curl -s -o nul http://localhost:11434/api/tags
if not errorlevel 1 goto :ollamaok
echo [NG] Ollama が動いていません。
echo      https://ollama.com/ からインストールして起動してから、
echo      もう一度 setup.bat を実行すると、モデルの確認まで進みます。
pause
exit /b 1

:ollamaok
set MODEL=
for /f "delims=" %%M in ('python -c "import muchio_llm as m; m.load_cfg(); print(m.CFG['model'])"') do set MODEL=%%M
if "%MODEL%"=="" goto :modeldone
ollama list | findstr /C:"%MODEL%" >nul
if not errorlevel 1 goto :modeldone
echo きていのモデル %MODEL% がまだ入っていません。数十GBあります。
echo 小さく試すなら例: ollama pull qwen3:4b  ※2GBくらい
choice /C YN /M "きていの大きいモデルをいまダウンロードしますか?"
if not errorlevel 2 ollama pull %MODEL%
echo ※入れないままでも、手持ちのモデルを自動で代用して動きます。設定画面で選び直せます。

:modeldone
rem Record the interpreter so run.bat always uses the same one as pip did.
python -c "import sys; open('python_path.txt', 'w').write(sys.executable)"

echo.
echo ==== セットアップ完了 ====
echo run.bat で起動すると、設定画面 http://localhost:8787 が自動で開きます。
echo さいしょに「なまえ」カードで ペットの名前 と あなたのVRChat表示名 を設定してね。
pause
