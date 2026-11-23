@echo off
rem Same as start.bat, but other laptops/phones in the same Wi-Fi can also open the site.
rem The address for them is printed in this window (http://192.168.x.x:8000/).
rem If Windows Firewall asks, click "Allow access".
cd /d "%~dp0"
call start.bat --network
