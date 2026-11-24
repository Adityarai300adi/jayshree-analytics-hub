@echo off
net session >nul 2>&1
if errorlevel 1 (
  echo Please right-click this file and choose "Run as administrator".
  pause
  exit /b 1
)
netsh advfirewall firewall delete rule name="Jayshree Analytics Hub" >nul 2>&1
netsh advfirewall firewall add rule name="Jayshree Analytics Hub" dir=in action=allow protocol=TCP localport=8085-8095 profile=any
echo.
echo Done. Phones and PCs on the same WiFi can now reach the server (ports 8085-8095).
pause
