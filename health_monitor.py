#!/usr/bin/env python3
"""
External Health Monitor for Flask Webhook Server
This script runs independently and can detect when the main server hangs
"""

import requests
import time
import threading
import psutil
import os
from datetime import datetime
import json

class ServerHealthMonitor:
    def __init__(self, server_url="http://localhost:5000", check_interval=10):
        self.server_url = server_url
        self.check_interval = check_interval
        self.last_successful_check = None
        self.consecutive_failures = 0
        self.running = True
        
    def check_endpoint(self, endpoint, timeout=5):
        """Check a specific endpoint with timeout"""
        try:
            response = requests.get(f"{self.server_url}{endpoint}", timeout=timeout)
            return {
                'success': True,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'content': response.text[:200] if response.text else None
            }
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'TIMEOUT', 'timeout': timeout}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'error': 'CONNECTION_REFUSED'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_python_processes(self):
        """Get all Python processes and their resource usage"""
        python_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info', 'num_threads']):
            try:
                if 'python' in proc.info['name'].lower():
                    python_processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cpu_percent': proc.info['cpu_percent'],
                        'memory_mb': proc.info['memory_info'].rss / 1024 / 1024,
                        'num_threads': proc.info['num_threads']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return python_processes
    
    def run_health_check(self):
        """Run a comprehensive health check"""
        timestamp = datetime.now().isoformat()
        
        # Check multiple endpoints
        health_check = self.check_endpoint('/health', timeout=3)
        ping_check = self.check_endpoint('/ping', timeout=3)
        debug_check = self.check_endpoint('/debug/locks', timeout=5)
        
        # Get system info
        python_processes = self.get_python_processes()
        
        # Determine overall status
        if health_check['success'] and ping_check['success']:
            status = "HEALTHY"
            self.consecutive_failures = 0
            self.last_successful_check = timestamp
        elif health_check['success'] or ping_check['success']:
            status = "DEGRADED"
            self.consecutive_failures += 1
        else:
            status = "FAILED"
            self.consecutive_failures += 1
        
        # If debug endpoint fails but others work, server is partially hung
        if health_check['success'] and not debug_check['success']:
            status = "PARTIALLY_HUNG"
        
        report = {
            'timestamp': timestamp,
            'status': status,
            'consecutive_failures': self.consecutive_failures,
            'last_successful_check': self.last_successful_check,
            'endpoints': {
                'health': health_check,
                'ping': ping_check,
                'debug': debug_check
            },
            'system': {
                'python_processes': python_processes,
                'total_python_processes': len(python_processes)
            }
        }
        
        return report
    
    def print_status_line(self, report):
        """Print a concise status line"""
        timestamp = report['timestamp'][11:19]  # Just time part
        status = report['status']
        failures = report['consecutive_failures']
        
        # Color coding for terminal
        if status == "HEALTHY":
            color = "\033[92m"  # Green
        elif status == "DEGRADED" or status == "PARTIALLY_HUNG":
            color = "\033[93m"  # Yellow
        else:
            color = "\033[91m"  # Red
        reset = "\033[0m"
        
        print(f"{timestamp} | {color}{status:15}{reset} | Failures: {failures:2d} | Processes: {len(report['system']['python_processes'])}")
        
        # Print details for non-healthy status
        if status != "HEALTHY":
            for endpoint, result in report['endpoints'].items():
                if not result['success']:
                    print(f"  └─ {endpoint}: {result.get('error', 'UNKNOWN_ERROR')}")
    
    def save_detailed_report(self, report):
        """Save detailed report when issues are detected"""
        if report['status'] != "HEALTHY":
            filename = f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"  └─ Detailed report saved: {filename}")
    
    def monitor_loop(self):
        """Main monitoring loop"""
        print("="*80)
        print("🔍 Flask Webhook Server Health Monitor")
        print(f"📡 Monitoring: {self.server_url}")
        print(f"⏱️  Check interval: {self.check_interval} seconds")
        print("="*80)
        print("Time     | Status          | Failures | Processes")
        print("-"*80)
        
        while self.running:
            try:
                report = self.run_health_check()
                self.print_status_line(report)
                
                # Save detailed report for issues
                if report['status'] != "HEALTHY":
                    self.save_detailed_report(report)
                
                # Alert if server has been down too long
                if self.consecutive_failures >= 3:
                    print(f"\n🚨 ALERT: Server has failed {self.consecutive_failures} consecutive checks!")
                    if self.consecutive_failures == 3:
                        print("   Consider restarting the server or checking logs.")
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                print("\n\n🛑 Monitoring stopped by user")
                self.running = False
                break
            except Exception as e:
                print(f"\n❌ Monitor error: {e}")
                time.sleep(self.check_interval)

def main():
    monitor = ServerHealthMonitor(check_interval=5)  # Check every 5 seconds
    monitor.monitor_loop()

if __name__ == "__main__":
    main()
