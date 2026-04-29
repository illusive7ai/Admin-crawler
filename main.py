#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import sys
import socket
import subprocess
import json
import urllib.request
import urllib.error
import random
import time
import re
import os
from datetime import datetime
from urllib.parse import urlparse, urljoin
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QFrame, QPushButton, QSizePolicy,
                            QInputDialog, QLineEdit, QProgressBar)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint, QSize, QRect
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QColor, QPalette, QFont, QIcon, QPixmap

# Import for PDF generation
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("ReportLab not installed. PDF reports disabled. Install with: pip install reportlab")

# Import requests for advanced HTTP features
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("Requests library not available. Install with: pip install requests")

# DeepSeek API integration
try:
    from openai import OpenAI
    DEEPSEEK_AVAILABLE = True
except ImportError:
    DEEPSEEK_AVAILABLE = False
    print("OpenAI library not available. Install with: pip install openai")

class UserAgentRotator:
    """Advanced User-Agent rotator from the TikTok script pattern"""
    
    @staticmethod
    def get_random_ua():
        browser_name = random.choice(['Mozilla', 'Chrome', 'Safari', 'Firefox', 'Edge'])
        browser_platform = random.choice(['Win32', 'Mac', 'Linux', 'Windows NT 10.0', 'Windows NT 6.1'])
        
        if browser_name == 'Chrome':
            versions = ['120.0.0.0', '119.0.0.0', '118.0.0.0', '117.0.0.0']
            version = random.choice(versions)
            return f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36'
        elif browser_name == 'Firefox':
            versions = ['121.0', '120.0', '119.0', '118.0']
            version = random.choice(versions)
            return f'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{version}) Gecko/20100101 Firefox/{version}'
        elif browser_name == 'Safari':
            return 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        else:
            return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    
    @staticmethod
    def get_headers():
        return {
            'User-Agent': UserAgentRotator.get_random_ua(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': random.choice(['en-US,en;q=0.9', 'en-GB,en;q=0.8', 'en;q=0.9']),
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        }

class AdminPanelScanner(QThread):
    """Main scanning engine with AI integration"""
    
    # Signals for GUI updates
    log_signal = pyqtSignal(str, str, str)  # category, message, type
    progress_signal = pyqtSignal(int)
    found_panel_signal = pyqtSignal(str, str)  # url, details
    scan_complete_signal = pyqtSignal(dict)
    
    def __init__(self, target_url, api_key=None):
        super().__init__()
        self.target_url = self.normalize_url(target_url)
        self.api_key = api_key
        self.base_domain = urlparse(self.target_url).netloc
        self.found_panels = []
        self.cms_type = None
        self.cms_version = None
        self.security_score = 0
        self.security_issues = []
        self.hidden_paths = []
        
        # Load wordlists
        self.load_wordlists()
        
    def normalize_url(self, url):
        """Ensure URL has protocol"""
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        return url
    
    def load_wordlists(self):
        """Load illusive.txt and CMS-specific wordlists"""
        self.common_paths = []
        
        # Load illusive.txt
        if os.path.exists('illusive.txt'):
            with open('illusive.txt', 'r') as f:
                self.common_paths = [line.strip() for line in f if line.strip()]
        
        # CMS-specific wordlists
        self.cms_wordlists = {}
        cms_files = ['wordpress.txt', 'joomla.txt', 'laravel.txt', 'drupal.txt']
        for cms_file in cms_files:
            if os.path.exists(f'cms_paths/{cms_file}'):
                with open(f'cms_paths/{cms_file}', 'r') as f:
                    cms_name = cms_file.replace('.txt', '')
                    self.cms_wordlists[cms_name] = [line.strip() for line in f if line.strip()]
    
    def detect_cms_with_ai(self):
        """Use DeepSeek API to detect CMS from homepage"""
        if not DEEPSEEK_AVAILABLE or not self.api_key:
            self.log_signal.emit('WARNING', 'DeepSeek API not available, using fallback detection', 'warning')
            return self.fallback_cms_detection()
        
        try:
            self.log_signal.emit('AI', 'Analyzing site with DeepSeek AI...', 'info')
            
            # Fetch homepage
            headers = UserAgentRotator.get_headers()
            response = requests.get(self.target_url, headers=headers, timeout=10)
            html_content = response.text[:5000]  # First 5000 chars
            
            # Initialize DeepSeek client
            client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com"
            )
            
            prompt = f"""
            Analyze this website HTML and identify:
            1. The CMS platform (WordPress, Joomla, Laravel, Drupal, Custom, etc.)
            2. The version if detectable
            3. Likely admin panel paths based on the structure
            
            HTML Sample:
            {html_content}
            
            Respond in JSON format:
            {{"cms": "name", "version": "version or unknown", "confidence": "high/medium/low", "suggested_paths": ["/path1", "/path2"]}}
            """
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            self.cms_type = result.get('cms', 'Unknown').lower()
            self.cms_version = result.get('version', 'Unknown')
            
            # Add AI-suggested paths
            suggested_paths = result.get('suggested_paths', [])
            self.hidden_paths.extend(suggested_paths)
            
            self.log_signal.emit('AI', f'Detected CMS: {self.cms_type} (v{self.cms_version})', 'success')
            return True
            
        except Exception as e:
            self.log_signal.emit('ERROR', f'AI detection failed: {str(e)}', 'error')
            return self.fallback_cms_detection()
    
    def fallback_cms_detection(self):
        """Fallback CMS detection using headers and HTML patterns"""
        try:
            headers = UserAgentRotator.get_headers()
            response = requests.get(self.target_url, headers=headers, timeout=10)
            html = response.text.lower()
            server = response.headers.get('Server', '').lower()
            
            # WordPress detection
            if 'wp-content' in html or 'wp-includes' in html or 'wordpress' in html:
                self.cms_type = 'wordpress'
                self.log_signal.emit('CMS', 'Detected: WordPress (via HTML patterns)', 'success')
            # Joomla detection
            elif 'joomla' in html or 'com_content' in html or '/joomla/' in html:
                self.cms_type = 'joomla'
                self.log_signal.emit('CMS', 'Detected: Joomla', 'success')
            # Laravel detection
            elif 'laravel' in html or 'csrf-token' in html:
                self.cms_type = 'laravel'
                self.log_signal.emit('CMS', 'Detected: Laravel', 'success')
            else:
                self.cms_type = 'unknown'
                self.log_signal.emit('CMS', 'CMS not detected, using common paths only', 'warning')
            
            return True
        except Exception as e:
            self.log_signal.emit('ERROR', f'Fallback detection failed: {str(e)}', 'error')
            return False
    
    def crawl_hidden_paths(self):
        """Extract hidden paths from robots.txt, sitemap.xml, and JS files"""
        self.log_signal.emit('CRAWLER', 'Scanning for hidden paths in robots.txt, sitemap.xml, JS files...', 'info')
        
        paths_to_check = ['/robots.txt', '/sitemap.xml', '/sitemap_index.xml']
        
        for path in paths_to_check:
            try:
                url = urljoin(self.target_url, path)
                headers = UserAgentRotator.get_headers()
                response = requests.get(url, headers=headers, timeout=5)
                
                if response.status_code == 200:
                    self.log_signal.emit('CRAWLER', f'Found: {path}', 'success')
                    
                    # Parse robots.txt
                    if 'robots.txt' in path:
                        for line in response.text.split('\n'):
                            if 'Disallow:' in line or 'Allow:' in line:
                                extracted_path = line.split(':', 1)[1].strip()
                                if extracted_path and extracted_path != '/':
                                    self.hidden_paths.append(extracted_path)
                    
                    # Parse sitemap.xml
                    elif 'sitemap' in path:
                        urls_found = re.findall(r'<loc>(.*?)</loc>', response.text)
                        for found_url in urls_found:
                            parsed = urlparse(found_url)
                            if parsed.path not in self.hidden_paths:
                                self.hidden_paths.append(parsed.path)
                                
            except Exception as e:
                continue
        
        self.log_signal.emit('CRAWLER', f'Discovered {len(self.hidden_paths)} hidden paths', 'info')
    
    def check_security_headers(self, response):
        """Check for security headers and rate security posture"""
        security_headers = [
            'X-Frame-Options', 'X-XSS-Protection', 'X-Content-Type-Options',
            'Strict-Transport-Security', 'Content-Security-Policy', 'Referrer-Policy'
        ]
        
        missing = []
        for header in security_headers:
            if header not in response.headers:
                missing.append(header)
        
        if missing:
            self.security_issues.append(f"Missing security headers: {', '.join(missing)}")
            return 60
        return 100
    
    def detect_login_form(self, html):
        """Detect if page contains a login form"""
        login_indicators = ['login', 'username', 'password', 'signin', 'log in']
        html_lower = html.lower()
        
        for indicator in login_indicators:
            if indicator in html_lower:
                return True
        return False
    
    def scan_paths(self):
        """Scan all discovered paths for admin panels"""
        # Combine all paths to scan
        all_paths = set(self.common_paths + self.hidden_paths)
        
        # Add CMS-specific paths if CMS detected
        if self.cms_type in self.cms_wordlists:
            all_paths.update(self.cms_wordlists[self.cms_type])
            self.log_signal.emit('SCAN', f'Added {len(self.cms_wordlists[self.cms_type])} CMS-specific paths', 'info')
        
        # Convert to list and shuffle for stealth
        all_paths = list(all_paths)
        random.shuffle(all_paths)
        
        total = len(all_paths)
        self.log_signal.emit('SCAN', f'Starting scan of {total} potential paths', 'info')
        
        for idx, path in enumerate(all_paths):
            # Update progress
            progress = int((idx + 1) / total * 100)
            self.progress_signal.emit(progress)
            
            # Build URL
            test_url = urljoin(self.target_url, path)
            
            # Rotate user agent
            headers = UserAgentRotator.get_headers()
            
            try:
                # Make request
                response = requests.get(test_url, headers=headers, timeout=5, allow_redirects=True)
                
                # Check for successful response (2xx, 3xx, 4xx except 404)
                if response.status_code != 404:
                    # Found something interesting
                    panel_info = {
                        'url': test_url,
                        'status': response.status_code,
                        'size': len(response.text),
                        'has_login': self.detect_login_form(response.text),
                        'headers_score': self.check_security_headers(response)
                    }
                    
                    self.found_panels.append(panel_info)
                    
                    # Log the finding
                    status_icon = '✓' if response.status_code == 200 else '!'
                    login_indicator = '🔐 LOGIN' if panel_info['has_login'] else ''
                    self.log_signal.emit('FOUND', f'{status_icon} {test_url} (HTTP {response.status_code}) {login_indicator}', 'success')
                    
                    # Emit signal for GUI
                    self.found_panel_signal.emit(test_url, f"HTTP {response.status_code}")
                    
            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.ConnectionError:
                continue
            except Exception as e:
                continue
            
            # Small delay to avoid rate limiting
            time.sleep(0.1)
        
        self.scan_complete_signal.emit(self.generate_report_data())
    
    def generate_report_data(self):
        """Generate comprehensive report data"""
        report_data = {
            'target': self.target_url,
            'domain': self.base_domain,
            'scan_time': datetime.now().isoformat(),
            'cms': self.cms_type,
            'cms_version': self.cms_version,
            'total_panels_found': len(self.found_panels),
            'panels': self.found_panels,
            'security_issues': self.security_issues,
            'paths_scanned': len(self.common_paths) + len(self.hidden_paths)
        }
        
        # Calculate overall security score
        if self.found_panels:
            avg_header_score = sum(p['headers_score'] for p in self.found_panels) / len(self.found_panels)
            report_data['security_score'] = avg_header_score
        else:
            report_data['security_score'] = 100
        
        return report_data
    
    def generate_pdf_report(self, report_data):
        """Generate PDF report of findings"""
        if not PDF_SUPPORT:
            self.log_signal.emit('REPORT', 'PDF generation not available (install reportlab)', 'warning')
            return None
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"reports/admin_panel_report_{self.base_domain}_{timestamp}.pdf"
        
        # Create reports directory if it doesn't exist
        os.makedirs('reports', exist_ok=True)
        
        doc = SimpleDocTemplate(filename, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.darkblue)
        story.append(Paragraph(f"Admin Panel Scan Report", title_style))
        story.append(Spacer(1, 12))
        
        # Target info
        story.append(Paragraph(f"<b>Target:</b> {report_data['target']}", styles['Normal']))
        story.append(Paragraph(f"<b>Domain:</b> {report_data['domain']}", styles['Normal']))
        story.append(Paragraph(f"<b>Scan Time:</b> {report_data['scan_time']}", styles['Normal']))
        story.append(Paragraph(f"<b>CMS Detected:</b> {report_data['cms']} v{report_data['cms_version']}", styles['Normal']))
        story.append(Spacer(1, 12))
        
        # Findings
        story.append(Paragraph(f"<b>Admin Panels Found: {report_data['total_panels_found']}</b>", styles['Heading2']))
        story.append(Spacer(1, 6))
        
        if report_data['panels']:
            for panel in report_data['panels']:
                story.append(Paragraph(f"• {panel['url']} (HTTP {panel['status']})", styles['Normal']))
                if panel['has_login']:
                    story.append(Paragraph(f"  <i>✓ Login form detected</i>", styles['Italic']))
        else:
            story.append(Paragraph("No admin panels found.", styles['Normal']))
        
        story.append(Spacer(1, 12))
        
        # Security assessment
        story.append(Paragraph("<b>Security Assessment</b>", styles['Heading2']))
        story.append(Paragraph(f"Security Score: {report_data['security_score']}/100", styles['Normal']))
        
        if report_data['security_issues']:
            story.append(Paragraph("<b>Issues Found:</b>", styles['Heading3']))
            for issue in report_data['security_issues']:
                story.append(Paragraph(f"• {issue}", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        self.log_signal.emit('REPORT', f'PDF report saved: {filename}', 'success')
        return filename
    
    def run(self):
        """Main execution flow"""
        self.log_signal.emit('INIT', f'Starting scan on {self.target_url}', 'info')
        
        # Step 1: Detect CMS with AI
        self.detect_cms_with_ai()
        
        # Step 2: Crawl for hidden paths
        self.crawl_hidden_paths()
        
        # Step 3: Scan all paths
        self.scan_paths()
        
        self.log_signal.emit('COMPLETE', f'Scan completed! Found {len(self.found_panels)} admin panels', 'success')

class SatelliteTerminal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EARTH COORDINATES - ADMIN PANEL HUNTER")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("background-color: #0a0f14;")
        
        # Scanner thread reference
        self.scanner = None
        
        self.setWindowFlags(Qt.FramelessWindowHint)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Main vertical layout (title bar + content)
        self.root_layout = QVBoxLayout(self.central_widget)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)
        
        # Create custom title bar with window controls
        self.create_title_bar()
        
        # Content area
        self.content_widget = QWidget()
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        
        # Create left sidebar with rotating earth
        self.create_sidebar()
        
        # Create right terminal panel
        self.create_terminal()
        
        self.root_layout.addWidget(self.content_widget)
        
        # Add scan controls to terminal
        self.add_scan_controls()
        
        # Fetch real IP data
        self.ip_fetcher = IPFetcher()
        self.ip_fetcher.ip_data_ready.connect(self.update_ip_data)
        self.ip_fetcher.start()
        
        # Terminal log timer
        self.log_timer = QTimer()
        self.log_timer.timeout.connect(self.add_log_entry)
        self.log_timer.start(800)
        
        self.log_entries = []
        self.current_log_index = 0
        
        # Window state tracking
        self.is_maximized = False
        self.normal_geometry = None
        
        # Fade in animation
        self.fade_in()
        
        # DeepSeek API key storage
        self.deepseek_api_key = None
    
    def add_scan_controls(self):
        """Add scan control buttons to the terminal area"""
        control_frame = QFrame()
        control_frame.setStyleSheet("""
            QFrame {
                background: #0d1218;
                border: 1px solid #1a3d2e;
                border-radius: 4px;
                margin-top: 10px;
                padding: 10px;
            }
        """)
        
        control_layout = QHBoxLayout(control_frame)
        control_layout.setSpacing(10)
        
        # Scan button
        self.scan_btn = QPushButton("▶ START SCAN")
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a3d2e;
                color: #4ade80;
                border: 1px solid #4ade80;
                border-radius: 4px;
                padding: 8px 20px;
                font-family: 'Courier New', monospace;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2a5d4e;
                border-color: #86efac;
            }
        """)
        self.scan_btn.clicked.connect(self.start_scan)
        control_layout.addWidget(self.scan_btn)
        
        # API Key button
        self.api_btn = QPushButton("🔑 SET DEEPSEEK API KEY")
        self.api_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e3a5f;
                color: #60a5fa;
                border: 1px solid #60a5fa;
                border-radius: 4px;
                padding: 8px 20px;
                font-family: 'Courier New', monospace;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2e4a6f;
            }
        """)
        self.api_btn.clicked.connect(self.set_api_key)
        control_layout.addWidget(self.api_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #1a3d2e;
                border-radius: 4px;
                text-align: center;
                color: #4ade80;
                background-color: #0a0f14;
            }
            QProgressBar::chunk {
                background-color: #4ade80;
                border-radius: 3px;
            }
        """)
        self.progress_bar.setVisible(False)
        control_layout.addWidget(self.progress_bar)
        
        # Find the terminal layout and add controls at the bottom
        terminal_layout = self.terminal.layout()
        terminal_layout.addWidget(control_frame)
    
    def set_api_key(self):
        """Prompt user for DeepSeek API key"""
        key, ok = QInputDialog.getText(self, 'DeepSeek API Key', 
                                        'Enter your DeepSeek API Key:\n(Get from https://platform.deepseek.com/)',
                                        QLineEdit.Password)
        if ok and key:
            self.deepseek_api_key = key
            self.add_terminal_log('API', 'DeepSeek API key configured successfully', 'success')
    
    def start_scan(self):
        """Start the admin panel scan"""
        # Get target URL
        target, ok = QInputDialog.getText(self, 'Target Website', 
                                          'Enter target website URL:\n(ex: example.com or https://example.com)')
        if not ok or not target:
            return
        
        if not self.deepseek_api_key:
            self.add_terminal_log('ERROR', 'Please set DeepSeek API key first!', 'error')
            return
        
        # Clear previous logs
        self.clear_terminal_logs()
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Create and start scanner thread
        self.scanner = AdminPanelScanner(target, self.deepseek_api_key)
        self.scanner.log_signal.connect(self.add_terminal_log)
        self.scanner.progress_signal.connect(self.progress_bar.setValue)
        self.scanner.found_panel_signal.connect(self.on_panel_found)
        self.scanner.scan_complete_signal.connect(self.on_scan_complete)
        self.scanner.start()
        
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("SCANNING...")
    
    def on_panel_found(self, url, details):
        """Handle found panel"""
        # Add a special visual indicator in the earth view for found panels
        js_code = f"""
        (function() {{
            var marker = document.getElementById('locationMarker');
            var label = document.getElementById('markerLabel');
            if (marker) {{
                label.textContent = 'PANEL FOUND';
                label.style.color = '#ff4444';
                setTimeout(function() {{
                    label.textContent = 'TARGET';
                    label.style.color = '#ff4444';
                }}, 2000);
            }}
        }})();
        """
        self.earth_view.page().runJavaScript(js_code)
    
    def on_scan_complete(self, report_data):
        """Handle scan completion"""
        self.progress_bar.setVisible(False)
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("▶ START SCAN")
        
        # Generate PDF report
        if self.scanner:
            self.scanner.generate_pdf_report(report_data)
    
    def add_terminal_log(self, category, message, log_type='normal'):
        """Add log to terminal view"""
        now = datetime.utcnow()
        timestamp = now.strftime('%H:%M:%S GMT')
        
        # Map category to color/style
        type_class = {
            'error': 'error',
            'warning': 'warning', 
            'success': 'success',
            'info': 'info'
        }.get(log_type, '')
        
        js_code = f"addLogEntry('{timestamp}', '{category}', '{message}', '{type_class}');"
        self.terminal_view.page().runJavaScript(js_code)
    
    def clear_terminal_logs(self):
        """Clear all terminal logs"""
        js_code = "clearLogs();"
        self.terminal_view.page().runJavaScript(js_code)
    
    def create_title_bar(self):
        # ... (keep your existing title bar code)
        self.title_bar = QFrame()
        self.title_bar.setFixedHeight(35)
        self.title_bar.setStyleSheet("""
            QFrame {
                background-color: #0d1218;
                border-bottom: 1px solid #1a3d2e;
            }
        """)
        
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(15, 0, 0, 0)
        title_layout.setSpacing(0)
        
        # Window title
        self.title_label = QLabel("ADMIN PANEL HUNTER // AI-POWERED SECURITY SCANNER")
        self.title_label.setStyleSheet("""
            color: #2563eb;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            letter-spacing: 2px;
            font-weight: bold;
        """)
        title_layout.addWidget(self.title_label)
        
        title_layout.addStretch()
        
        # Window control buttons
        btn_style = """
            QPushButton {
                background-color: transparent;
                color: #4ade80;
                border: none;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: normal;
                padding: 0;
                margin: 0;
                min-width: 45px;
                max-width: 45px;
                min-height: 35px;
                max-height: 35px;
            }
            QPushButton:hover {
                background-color: #1a3d2e;
                color: #86efac;
            }
        """
        
        close_btn_style = """
            QPushButton {
                background-color: transparent;
                color: #4ade80;
                border: none;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
                font-weight: normal;
                padding: 0;
                margin: 0;
                min-width: 45px;
                max-width: 45px;
                min-height: 35px;
                max-height: 35px;
            }
            QPushButton:hover {
                background-color: #ef4444;
                color: #ffffff;
            }
        """
        
        self.btn_minimize = QPushButton("−")
        self.btn_minimize.setStyleSheet(btn_style)
        self.btn_minimize.clicked.connect(self.showMinimized)
        title_layout.addWidget(self.btn_minimize)
        
        self.btn_close = QPushButton("×")
        self.btn_close.setStyleSheet(close_btn_style)
        self.btn_close.clicked.connect(self.close)
        title_layout.addWidget(self.btn_close)
        
        self.root_layout.addWidget(self.title_bar)
        
        # Enable dragging
        self.title_bar.mousePressEvent = self.title_bar_mouse_press
        self.title_bar.mouseMoveEvent = self.title_bar_mouse_move
        self.title_bar.mouseDoubleClickEvent = lambda e: self.toggle_maximize()
    
    def title_bar_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def title_bar_mouse_move(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_pos and not self.is_maximized:
            self.move(event.globalPos() - self.drag_pos)
            event.accept()
    
    def toggle_maximize(self):
        if self.is_maximized:
            self.showNormal()
            self.is_maximized = False
        else:
            self.showMaximized()
            self.is_maximized = True
    
    def fade_in(self):
        self.setWindowOpacity(0)
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(1000)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()
    
    def create_sidebar(self):
        # ... (keep your existing sidebar code - it's the same as before)
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(420)
        self.sidebar.setStyleSheet("""
            QFrame {
                background-color: #0d1218;
                border-right: 2px solid #1a3d2e;
            }
        """)
        
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(20, 20, 20, 20)
        sidebar_layout.setSpacing(15)
        
        title = QLabel("ADMIN PANEL HUNTER")
        title.setStyleSheet("""
            color: #2563eb;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            font-weight: bold;
            letter-spacing: 3px;
            border-bottom: 1px solid #1a3d2e;
            padding-bottom: 10px;
        """)
        sidebar_layout.addWidget(title)
        
        # Earth visualization
        self.earth_view = QWebEngineView()
        self.earth_view.setFixedSize(380, 380)
        self.earth_view.setStyleSheet("background: transparent; border: none;")
        
        earth_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    margin: 0;
                    background: #0a0f14;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    overflow: hidden;
                }
                
                .earth-container {
                    position: relative;
                    width: 300px;
                    height: 300px;
                    margin: 40px;
                }
                
                .earth {
                    width: 300px;
                    height: 300px;
                    border-radius: 50%;
                    background: linear-gradient(135deg, #1a4d3e 0%, #0d2a20 100%);
                    box-shadow: inset -40px -40px 100px rgba(0, 0, 0, 0.9), inset 20px 20px 60px rgba(255, 255, 255, 0.2), 0 0 60px rgba(74, 222, 128, 0.3);
                    position: relative;
                    overflow: hidden;
                    animation: rotateEarth 20s linear infinite;
                }
                
                .earth:before {
                    content: '';
                    position: absolute;
                    width: 200%;
                    height: 200%;
                    background: url('https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74092/world.200407.3x5400x2700.jpg');
                    background-size: 50% 50%;
                    background-position: 0 0;
                    background-repeat: no-repeat;
                    animation: rotateTexture 20s linear infinite;
                }
                
                @keyframes rotateEarth {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
                
                @keyframes rotateTexture {
                    from { background-position: 0 0; }
                    to { background-position: 100% 0; }
                }
                
                .night-shadow {
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    border-radius: 50%;
                    background: linear-gradient(135deg, rgba(0,0,0,0) 50%, rgba(0,0,0,0.6) 100%);
                    pointer-events: none;
                }
            </style>
        </head>
        <body>
            <div class="earth-container">
                <div class="earth"></div>
                <div class="night-shadow"></div>
            </div>
        </body>
        </html>
        """
        
        self.earth_view.setHtml(earth_html)
        sidebar_layout.addWidget(self.earth_view, alignment=Qt.AlignCenter)
        
        self.coords_label = QLabel("ADMIN PANEL HUNTER v2.0")
        self.coords_label.setStyleSheet("""
            color: #d1d5db;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            text-align: center;
            padding: 12px;
            background: rgba(74, 222, 128, 0.05);
            border: 1px solid #1a3d2e;
            border-radius: 4px;
            margin-top: 10px;
        """)
        self.coords_label.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(self.coords_label)
        
        sidebar_layout.addStretch()
        self.content_layout.addWidget(self.sidebar)
    
    def create_terminal(self):
        """Create terminal output area"""
        self.terminal = QFrame()
        self.terminal.setStyleSheet("""
            QFrame {
                background-color: #0a0f14;
                border-left: 1px solid #1a3d2e;
            }
        """)
        
        terminal_layout = QVBoxLayout(self.terminal)
        terminal_layout.setContentsMargins(20, 20, 20, 20)
        terminal_layout.setSpacing(10)
        
        # Header
        header = QLabel("[ADMIN PANEL HUNTER] — AI-POWERED SECURITY SCANNER")
        header.setStyleSheet("""
            color: #2563eb;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            font-weight: bold;
            letter-spacing: 2px;
            border-bottom: 1px solid #1a3d2e;
            padding-bottom: 10px;
            margin-bottom: 10px;
        """)
        terminal_layout.addWidget(header)
        
        # Terminal output area
        self.terminal_view = QWebEngineView()
        self.terminal_view.setStyleSheet("background: #0a0f14;")
        
        terminal_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    margin: 0;
                    padding: 10px;
                    background: #0a0f14;
                    color: #4ade80;
                    font-family: 'Courier New', monospace;
                    font-size: 12px;
                    line-height: 1.6;
                    overflow-y: auto;
                    height: 100vh;
                }
                
                .log-entry {
                    margin: 2px 0;
                    opacity: 0;
                    animation: fadeIn 0.3s ease-in forwards;
                    display: flex;
                    align-items: flex-start;
                }
                
                .timestamp {
                    color: #22c55e;
                    margin-right: 10px;
                    min-width: 85px;
                }
                
                .category {
                    color: #86efac;
                    margin-right: 10px;
                    min-width: 70px;
                }
                
                .message {
                    color: #4ade80;
                    flex: 1;
                }
                
                .error { color: #ef4444; }
                .warning { color: #fbbf24; }
                .info { color: #60a5fa; }
                .success { color: #4ade80; }
                
                @keyframes fadeIn {
                    from { opacity: 0; transform: translateX(-10px); }
                    to { opacity: 1; transform: translateX(0); }
                }
                
                .status-bar {
                    position: fixed;
                    bottom: 0;
                    left: 0;
                    right: 0;
                    background: #0d1218;
                    border-top: 1px solid #1a3d2e;
                    padding: 8px 15px;
                    display: flex;
                    justify-content: space-between;
                    font-size: 11px;
                }
                
                .status-indicator {
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background: #4ade80;
                    animation: pulse 2s ease-in-out infinite;
                    display: inline-block;
                    margin-right: 8px;
                }
                
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
                
                #log-container {
                    padding-bottom: 40px;
                }
            </style>
        </head>
        <body>
            <div id="log-container"></div>
            <div class="status-bar">
                <div><span class="status-indicator"></span> SYSTEM: READY</div>
                <div>AI ENGINE: STANDBY</div>
                <div>SCANNER: IDLE</div>
            </div>
            <script>
                function addLogEntry(timestamp, category, message, type) {
                    const container = document.getElementById('log-container');
                    const entry = document.createElement('div');
                    entry.className = 'log-entry';
                    const typeClass = type || '';
                    entry.innerHTML = `
                        <span class="timestamp">${timestamp}</span>
                        <span class="category">[${category}]</span>
                        <span class="message ${typeClass}">${message}</span>
                    `;
                    container.appendChild(entry);
                    
                    while (container.children.length > 100) {
                        container.removeChild(container.firstChild);
                    }
                    
                    window.scrollTo(0, document.body.scrollHeight);
                }
                
                function clearLogs() {
                    document.getElementById('log-container').innerHTML = '';
                }
            </script>
        </body>
        </html>
        """
        
        self.terminal_view.setHtml(terminal_html)
        terminal_layout.addWidget(self.terminal_view)
        
        self.content_layout.addWidget(self.terminal, stretch=1)
    
    def update_ip_data(self, data):
        """Update IP data in sidebar"""
        lat = data.get('latitude') or 36.8820
        lon = data.get('longitude') or -97.3411
        
        self.coords_label.setText(f"TARGET: READY • LAT: {lat:.2f} • LON: {lon:.2f}")
    
    def add_log_entry(self):
        """Add simulated log entries for atmosphere"""
        categories = ['SYSTEM', 'NETWORK', 'SCANNER', 'AI', 'SECURITY']
        messages = [
            ('System ready for scan', 'info'),
            ('AI engine initialized', 'success'),
            ('Wordlists loaded', 'info'),
            ('Waiting for target', 'normal'),
            ('DeepSeek API: Standby', 'info')
        ]
        
        if self.current_log_index < len(self.log_entries):
            cat, msg, typ = self.log_entries[self.current_log_index]
            self.current_log_index += 1
        else:
            cat = random.choice(categories)
            msg, typ = random.choice(messages)
        
        now = datetime.utcnow()
        timestamp = now.strftime('%H:%M:%S GMT')
        
        js_code = f"addLogEntry('{timestamp}', '{cat}', '{msg}', '{typ}');"
        self.terminal_view.page().runJavaScript(js_code)
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()


class IPFetcher(QThread):
    ip_data_ready = pyqtSignal(dict)
    
    def run(self):
        try:
            public_ip = subprocess.run(
                ["powershell", "-Command", "Invoke-RestMethod -Uri https://api.ipify.org"],
                capture_output=True, text=True, timeout=10
            ).stdout.strip()
            
            hostname = socket.gethostname()
            private_ip = socket.getaddrinfo(hostname, None, socket.AF_INET)[0][4][0]
            
            data = {
                'public_ip': public_ip,
                'private_ip': private_ip,
                'latitude': 36.8820,
                'longitude': -97.3411,
                'city': 'Unknown',
                'region': 'Unknown',
                'country': 'Unknown'
            }
            
            self.ip_data_ready.emit(data)
        except Exception as e:
            self.ip_data_ready.emit({
                'public_ip': 'Error',
                'private_ip': 'Error',
                'latitude': 36.8820,
                'longitude': -97.3411
            })


if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    font = QFont('Courier New', 10)
    font.setStyleHint(QFont.Monospace)
    app.setFont(font)
    
    window = SatelliteTerminal()
    window.show()
    sys.exit(app.exec_())