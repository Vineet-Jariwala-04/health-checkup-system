@echo off
title AI-Based Human Body Prediction System
echo ============================================================
echo  AI-Based Human Body Prediction System
echo ============================================================
echo.
echo Starting Flask backend API (app.py) in a new window...
start "Flask Backend API - do not close" cmd /k python app.py

echo Waiting a few seconds for the backend to finish loading models...
timeout /t 5 /nobreak >nul

echo Starting Streamlit frontend (streamlit_app.py)...
echo.
python -m streamlit run streamlit_app.py

echo.
echo Streamlit has stopped. Remember to also close the
echo "Flask Backend API" window if you are done.
pause
