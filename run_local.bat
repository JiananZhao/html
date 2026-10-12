@echo off
title Macro & Equity Research Terminal
echo ======================================================
echo  Starting Macro & Equity Research Terminal (Streamlit)
echo ======================================================
set PATH=D:\ProgramData\Anaconda3;D:\ProgramData\Anaconda3\Scripts;D:\ProgramData\Anaconda3\Library\bin;C:\Users\jiana\AppData\Roaming\Python\Python39\Scripts;%PATH%
D:\ProgramData\Anaconda3\python.exe -m streamlit run rd_data.py --theme.base dark --theme.backgroundColor "#0b0f19" --theme.secondaryBackgroundColor "#131b2a" --theme.textColor "#f8fafc" --theme.primaryColor "#3b82f6"
pause
