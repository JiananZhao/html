@echo off
title Macro & Equity Research Terminal
echo ======================================================
echo  Starting Macro & Equity Research Terminal (Streamlit)
echo ======================================================
set PATH=D:\ProgramData\Anaconda3;D:\ProgramData\Anaconda3\Scripts;D:\ProgramData\Anaconda3\Library\bin;C:\Users\jiana\AppData\Roaming\Python\Python39\Scripts;%PATH%
D:\ProgramData\Anaconda3\python.exe -m streamlit run rd_data.py
pause
