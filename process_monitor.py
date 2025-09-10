#!/usr/bin/env python3
"""
Simple Process Monitor for Flask Server
Monitors CPU, memory, and thread count of Python processes
"""

import psutil
import time
import os
from datetime import datetime

def find_flask_processes():
    """Find Python processes that might be the Flask server"""
    flask_processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        try:
            if ('python' in proc.info['name'].lower() and 
                proc.info['cmdline'] and 
                any('flask' in str(arg).lower() for arg in proc.info['cmdline'])):
                flask_processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return flask_processes

def monitor_process(proc, duration=60):
    """Monitor a specific process for a duration"""
    print(f"\n🔍 Monitoring PID {proc.pid} for {duration} seconds...")
    print("Time     | CPU%  | Memory(MB) | Threads | Status")
    print("-" * 50)
    
    start_time = time.time()
    samples = []
    
    while time.time() - start_time < duration:
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            cpu_percent = proc.cpu_percent(interval=1)
            memory_mb = proc.memory_info().rss / 1024 / 1024
            num_threads = proc.num_threads()
            status = proc.status()
            
            sample = {
                'timestamp': timestamp,
                'cpu_percent': cpu_percent,
                'memory_mb': memory_mb,
                'num_threads': num_threads,
                'status': status
            }
            samples.append(sample)
            
            # Alert on suspicious patterns
            alert = ""
            if cpu_percent > 50:
                alert += " HIGH_CPU"
            if num_threads > 20:
                alert += " HIGH_THREADS"
            if status != 'running':
                alert += f" STATUS_{status.upper()}"
            
            print(f"{timestamp} | {cpu_percent:5.1f} | {memory_mb:10.1f} | {num_threads:7d} | {status:8s}{alert}")
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"{timestamp} | PROCESS TERMINATED")
            break
        except KeyboardInterrupt:
            print("\n🛑 Monitoring stopped by user")
            break
    
    # Summary
    if samples:
        avg_cpu = sum(s['cpu_percent'] for s in samples) / len(samples)
        max_memory = max(s['memory_mb'] for s in samples)
        max_threads = max(s['num_threads'] for s in samples)
        
        print("\n📊 Summary:")
        print(f"   Average CPU: {avg_cpu:.1f}%")
        print(f"   Peak Memory: {max_memory:.1f} MB")
        print(f"   Peak Threads: {max_threads}")
        print(f"   Total Samples: {len(samples)}")

def main():
    print("🔍 Flask Process Monitor")
    print("=" * 50)
    
    # Find Flask processes
    flask_processes = find_flask_processes()
    
    if not flask_processes:
        print("❌ No Flask processes found!")
        print("\n💡 Start your Flask server first:")
        print("   python flask_webhook_server.py")
        return
    
    print(f"✅ Found {len(flask_processes)} Flask process(es):")
    for i, proc in enumerate(flask_processes):
        try:
            cmdline = ' '.join(proc.cmdline()[:3])  # First 3 args
            print(f"   {i+1}. PID {proc.pid}: {cmdline}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"   {i+1}. PID {proc.pid}: <access denied>")
    
    # Monitor the first (or only) process
    if flask_processes:
        target_proc = flask_processes[0]
        monitor_process(target_proc, duration=300)  # Monitor for 5 minutes

if __name__ == "__main__":
    main()
