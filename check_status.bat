@echo off
cd /d C:\Dev\Berry-Gym
set "GIT=C:\Program Files\Git\cmd\git.exe"
"%GIT%" branch --show-current > C:\Dev\Berry-Gym\git_status.txt 2>&1
echo --- >> C:\Dev\Berry-Gym\git_status.txt
"%GIT%" status --short >> C:\Dev\Berry-Gym\git_status.txt 2>&1
echo --- >> C:\Dev\Berry-Gym\git_status.txt
"%GIT%" log --oneline -5 >> C:\Dev\Berry-Gym\git_status.txt 2>&1
