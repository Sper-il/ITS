"""Trigger routing page load and print graph stats."""
import subprocess, sys, time

# Start a fresh server
proc = subprocess.Popen(
    [sys.executable, "-m", "streamlit", "run", "app.py",
     "--server.headless", "true", "--server.port", "8502",
     "--browser.gatherUsageStats", "false"],
    cwd=r"c:\Users\Admin\Downloads\ITS\TRAFFIC_PROCESSING",
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)
time.sleep(10)

# Read initial output
proc.terminate()
stdout, _ = proc.communicate(timeout=5)
print(stdout.decode("utf-8", errors="replace"))
