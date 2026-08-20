@echo off
setlocal EnableExtensions EnableDelayedExpansion
title AI Pick Vault - Tools
color 0A

REM ============================================================
REM  Update-AIPickVault.bat
REM  Desktop menu for AI Pick Vault price pipeline + site tools.
REM  Requires: GitHub CLI (gh auth login), Python for local options.
REM  Full pipeline order (this PC menu): Amazon scan then eBay scan.
REM  (GitHub schedule still chains eBay -> Amazon overnight.)
REM  Rebuilt: 2026-08-20  (copy lives on OneDrive Desktop)
REM ============================================================

where gh >nul 2>&1
if errorlevel 1 (
  echo.
  echo ERROR: GitHub CLI "gh" not found on PATH.
  echo Install: https://cli.github.com/
  echo Then run:  gh auth login
  echo.
  pause
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  echo.
  echo WARNING: Python not found on PATH. Local options 9-12 will fail.
  echo Cloud GitHub Actions options still work.
  echo.
  timeout /t 3 >nul
)

set "REPO=bamtec70/aipickvault"
set "SITE=https://aipickvault.com"
set "LOCAL=C:\Users\bamte\aipickvault"
set "FAIL_COUNT=0"

REM Workflow display names must match the "name:" field in each .yml
set "WF_EBAY=Daily price refresh"
set "WF_AMZ_WATCH=Amazon snapshot watch"
set "WF_AMZ_APPLY=Amazon snapshot apply"
set "WF_AUDIT=Price scan audit"
set "WF_VERIFY=Catalog price verify"
set "WF_TD=Sync Truth Desk videos"
set "WF_TIKTOK=Sync TikTok vault"

:menu
cls
echo.
echo ============================================================
echo   AI Pick Vault - Tools
echo ============================================================
echo   Site:  %SITE%
echo   Repo:  %REPO%
echo   Local: %LOCAL%
echo.
echo   OVERNIGHT on GitHub ^(automatic^):
echo     eBay Daily -^> Amazon watch -^> Amazon apply -^> Pages
echo.
echo   THIS MENU full pipeline ^(option 1^):
echo     Amazon watch -^> Amazon apply -^> eBay Daily
echo     ^(Amazon baseline prices first, then eBay scan^)
echo.
echo   eBay prices go live via API when Daily completes.
echo   Amazon prices go live after apply pushes + Pages rebuild.
echo.
echo   --- RECOMMENDED ---
echo     1^) FULL PRICE PIPELINE  ^(Amazon then eBay^)
echo         Amazon watch -^> Amazon apply -^> Daily eBay refresh
echo.
echo   --- PRICES ^(individual GitHub Actions^) ---
echo     2^) Amazon snapshot watch only
echo     3^) Amazon snapshot apply only  ^(live-fetch + push if needed^)
echo     4^) Daily price refresh only  ^(eBay worker^)
echo     5^) Price scan audit
echo     6^) Catalog price verify
echo.
echo   --- SITE CONTENT ---
echo     7^) Sync Truth Desk videos
echo     8^) Sync TikTok vault
echo.
echo   --- LOCAL ^(this PC^) ---
echo     9^) Local: verify catalog prices ^(full + Amazon scrape^)
echo    10^) Local: verify catalog+eBay only  ^(--skip-amazon^)
echo    11^) Local: apply Amazon prices to index.html
echo    12^) Local: extract catalog from index.html
echo.
echo   --- OTHER ---
echo    13^) Open aipickvault.com
echo    14^) Show recent GitHub Action runs
echo    15^) Open local repo folder
echo     0^) Exit
echo.
echo ============================================================
set "CHOICE="
set /p CHOICE=Enter choice [0-15]: 

if "%CHOICE%"=="1" goto full_pipeline
if "%CHOICE%"=="2" goto amz_watch
if "%CHOICE%"=="3" goto amz_apply
if "%CHOICE%"=="4" goto daily
if "%CHOICE%"=="5" goto audit
if "%CHOICE%"=="6" goto verify_ci
if "%CHOICE%"=="7" goto td_videos
if "%CHOICE%"=="8" goto tiktok
if "%CHOICE%"=="9" goto local_verify
if "%CHOICE%"=="10" goto local_verify_fast
if "%CHOICE%"=="11" goto local_amz_apply
if "%CHOICE%"=="12" goto local_extract
if "%CHOICE%"=="13" goto open_site
if "%CHOICE%"=="14" goto runs
if "%CHOICE%"=="15" goto open_repo
if "%CHOICE%"=="0" goto end
echo Invalid choice.
timeout /t 2 >nul
goto menu

REM ---------- FULL PIPELINE: Amazon first, then eBay ----------
:full_pipeline
set "FAIL_COUNT=0"
echo.
echo ============================================================
echo   FULL PRICE PIPELINE
echo   Amazon watch -^> Amazon apply -^> eBay Daily -^> Pages
echo ============================================================
echo.
echo [1/3] Amazon snapshot watch ^(detect drift vs site^)...
call :queue_and_watch "%WF_AMZ_WATCH%" ""
if !FAIL_COUNT! GTR 0 (
  echo.
  echo Amazon watch failed ? still attempting apply, then eBay.
)
echo.
echo [2/3] Amazon snapshot apply ^(live-fetch; may push index.html^)...
call :queue_and_watch "%WF_AMZ_APPLY%" "-f source=live-fetch -f dry_run=false"
echo.
echo [3/3] Daily price refresh ^(eBay worker + Amazon-baseline scan^)...
call :queue_and_watch "%WF_EBAY%" ""
echo.
echo Pipeline finished watching.
echo - Amazon: if apply pushed, wait ~1 min for Pages then Ctrl+F5
echo - eBay: live on site via API ^(refresh the page^)
goto summary

:amz_watch
set "FAIL_COUNT=0"
echo.
echo Amazon snapshot watch only.
echo After success, apply can be run with option 3 ^(or auto-chain if
echo this was triggered from the overnight eBay pipeline^).
echo.
call :queue_and_watch "%WF_AMZ_WATCH%" ""
echo.
echo Watching Amazon apply if it auto-starts after watch...
timeout /t 8 /nobreak >nul
call :wait_and_watch_new "%WF_AMZ_APPLY%" 60
goto summary

:amz_apply
set "FAIL_COUNT=0"
echo.
echo Amazon snapshot apply ^(live-fetch; may push index.html for Pages^)...
call :queue_and_watch "%WF_AMZ_APPLY%" "-f source=live-fetch -f dry_run=false"
goto summary

:daily
set "FAIL_COUNT=0"
echo.
echo Daily price refresh only ^(eBay^).
echo Amazon is NOT auto-started by this menu option.
echo Use option 1 for Amazon-then-eBay, or 2/3 for Amazon alone.
echo.
call :queue_and_watch "%WF_EBAY%" ""
goto summary

:audit
set "FAIL_COUNT=0"
call :queue_and_watch "%WF_AUDIT%" ""
goto summary

:verify_ci
set "FAIL_COUNT=0"
call :queue_and_watch "%WF_VERIFY%" ""
goto summary

:td_videos
set "FAIL_COUNT=0"
call :queue_and_watch "%WF_TD%" ""
goto summary

:tiktok
set "FAIL_COUNT=0"
call :queue_and_watch "%WF_TIKTOK%" ""
goto summary

:local_verify
set "FAIL_COUNT=0"
call :need_repo
if errorlevel 1 goto summary
echo.
echo Local full verify ^(Amazon scrape can take ~2 min^)...
echo.
cd /d "%LOCAL%"
python ebay-worker\verify_catalog_prices.py
if errorlevel 1 set /a FAIL_COUNT+=1
goto summary

:local_verify_fast
set "FAIL_COUNT=0"
call :need_repo
if errorlevel 1 goto summary
echo.
echo Local verify catalog + eBay only...
echo.
cd /d "%LOCAL%"
python ebay-worker\verify_catalog_prices.py --skip-amazon
if errorlevel 1 set /a FAIL_COUNT+=1
goto summary

:local_amz_apply
set "FAIL_COUNT=0"
call :need_repo
if errorlevel 1 goto summary
echo.
echo Applying live Amazon prices into index.html...
echo.
cd /d "%LOCAL%"
if not exist "ebay-worker\_audit" mkdir "ebay-worker\_audit"
python ebay-worker\amazon_snapshot_watch.py --index index.html --apply --report ebay-worker\_audit\desktop_amazon_apply.json --checklist ebay-worker\_audit\desktop_amazon_apply.md --sleep 1.0
if errorlevel 1 (
  set /a FAIL_COUNT+=1
) else (
  echo.
  echo Done. If index.html changed, commit/push when ready:
  echo   cd /d %LOCAL%
  echo   git add index.html
  echo   git commit -m "chore: apply Amazon prices"
  echo   git push
)
goto summary

:local_extract
set "FAIL_COUNT=0"
call :need_repo
if errorlevel 1 goto summary
echo.
echo Extracting catalog from index.html ^(includes amazonPrice baselines^)...
echo.
cd /d "%LOCAL%"
python ebay-worker\extract_catalog.py
if errorlevel 1 set /a FAIL_COUNT+=1
echo.
echo If catalog changed: deploy worker, then run option 4 ^(eBay Daily^).
echo   cd /d %LOCAL%\ebay-worker
echo   node node_modules\wrangler\bin\wrangler.js deploy
goto summary

:open_site
start "" "%SITE%"
goto menu

:open_repo
if exist "%LOCAL%" (
  explorer "%LOCAL%"
) else (
  echo Repo folder not found: %LOCAL%
  pause
)
goto menu

:runs
echo.
echo Recent runs for %REPO%:
echo.
gh run list --repo %REPO% --limit 20
echo.
pause
goto menu

REM ---------- helpers ----------

:need_repo
if not exist "%LOCAL%\ebay-worker" (
  echo.
  echo ERROR: Local repo not found:
  echo   %LOCAL%
  echo.
  set /a FAIL_COUNT+=1
  exit /b 1
)
if not exist "%LOCAL%\index.html" (
  echo.
  echo ERROR: index.html missing under:
  echo   %LOCAL%
  echo.
  set /a FAIL_COUNT+=1
  exit /b 1
)
exit /b 0

:queue_wf
set "WF=%~1"
set "FLAGS=%~2"
echo   Queuing: !WF!
if "!FLAGS!"=="" (
  gh workflow run "!WF!" --repo %REPO% --ref main
) else (
  REM FLAGS must expand without quotes around whole string
  gh workflow run "!WF!" --repo %REPO% --ref main !FLAGS!
)
if errorlevel 1 (
  echo   FAILED to queue !WF!
  echo   Tip: gh workflow list --repo %REPO%
  set /a FAIL_COUNT+=1
  exit /b 1
) else (
  echo   Queued OK
)
exit /b 0

:watch_run_id
set "RID=%~1"
if "!RID!"=="" (
  echo   No run ID to watch.
  set /a FAIL_COUNT+=1
  goto :eof
)
echo   Run ID: !RID!
echo   URL:    https://github.com/%REPO%/actions/runs/!RID!
echo.
echo   --- live progress ^(Ctrl+C stops watching only; job keeps running on GitHub^) ---
echo.
gh run watch !RID! --repo %REPO% --exit-status
if errorlevel 1 (
  echo.
  echo   RESULT: FAILED
  set /a FAIL_COUNT+=1
  echo.
  echo   --- failed step logs ---
  gh run view !RID! --repo %REPO% --log-failed 2>nul
) else (
  echo.
  echo   RESULT: SUCCEEDED
)
echo.
goto :eof

:watch_latest
set "WF=%~1"
echo.
echo ------------------------------------------------------------
echo   WATCHING: !WF!
echo ------------------------------------------------------------
set "RUN_ID="
for /f "usebackq delims=" %%I in (`gh run list --repo %REPO% --workflow "!WF!" --limit 1 --json databaseId --jq ".[0].databaseId" 2^>nul`) do set "RUN_ID=%%I"
if not defined RUN_ID (
  echo   Could not find a run ID for !WF!.
  echo   Check: https://github.com/%REPO%/actions
  set /a FAIL_COUNT+=1
  goto :eof
)
call :watch_run_id !RUN_ID!
goto :eof

:wait_and_watch_new
REM %1 = workflow name, %2 = max wait seconds for a new/in-progress run
set "WF=%~1"
set "MAXWAIT=%~2"
if "!MAXWAIT!"=="" set "MAXWAIT=90"
echo.
echo ------------------------------------------------------------
echo   Waiting for: !WF!
echo   ^(up to !MAXWAIT!s for a queued/in_progress run^)
echo ------------------------------------------------------------
set /a ELAPSED=0
set "RUN_ID="
set "STATUS="

:wait_loop
set "RUN_ID="
set "STATUS="
for /f "usebackq delims=" %%I in (`gh run list --repo %REPO% --workflow "!WF!" --limit 1 --json databaseId,status --jq ".[0] | \"\(.databaseId) \(.status)\"" 2^>nul`) do (
  for /f "tokens=1,2" %%A in ("%%I") do (
    set "RUN_ID=%%A"
    set "STATUS=%%B"
  )
)
if defined RUN_ID (
  if /i "!STATUS!"=="in_progress" goto watch_found
  if /i "!STATUS!"=="queued" goto watch_found
  if /i "!STATUS!"=="waiting" goto watch_found
  if /i "!STATUS!"=="requested" goto watch_found
  if /i "!STATUS!"=="pending" goto watch_found
  if /i "!STATUS!"=="completed" (
    if !ELAPSED! GEQ 15 goto watch_found
  )
)
if !ELAPSED! GEQ !MAXWAIT! (
  echo   Timed out waiting for !WF! to start.
  echo   It may still be queued behind the concurrency group.
  echo   Check: https://github.com/%REPO%/actions
  if defined RUN_ID (
    echo   Latest run: !RUN_ID! status=!STATUS!
    call :watch_run_id !RUN_ID!
  ) else (
    set /a FAIL_COUNT+=1
  )
  goto :eof
)
echo   ... waiting ^(!ELAPSED!s / !MAXWAIT!s^) status=!STATUS!
timeout /t 5 /nobreak >nul
set /a ELAPSED+=5
goto wait_loop

:watch_found
echo   Found run !RUN_ID! status=!STATUS!
call :watch_run_id !RUN_ID!
goto :eof

:queue_and_watch
set "WF=%~1"
set "FLAGS=%~2"
echo.
echo ============================================================
echo   !WF!
echo ============================================================
echo.
call :queue_wf "!WF!" "!FLAGS!"
if errorlevel 1 goto :eof
echo.
echo Waiting for GitHub to register the run...
timeout /t 6 /nobreak >nul
call :watch_latest "!WF!"
goto :eof

:summary
echo.
echo ============================================================
echo   DONE
echo ============================================================
if !FAIL_COUNT! GTR 0 (
  echo   Issues/failures noted: !FAIL_COUNT!
  echo   Actions: https://github.com/%REPO%/actions
) else (
  echo   Completed without recorded failures in this session.
)
echo.
echo   Site:    %SITE%   ^(Ctrl+F5 after Pages if Amazon apply pushed^)
echo   Actions: https://github.com/%REPO%/actions
echo.
echo   Menu full pipeline order:
echo     Amazon watch -^> Amazon apply -^> eBay Daily
echo ============================================================
echo.
set "AGAIN="
set /p AGAIN=Press Enter for menu, or type Q then Enter to quit: 
if /i "%AGAIN%"=="Q" goto end
goto menu

:end
endlocal
exit /b 0
