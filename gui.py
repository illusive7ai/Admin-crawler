import sys
import socket
import subprocess
import time
import json
import urllib.request
import random
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QFrame, QPushButton, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint, QSize, QRect
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtGui import QColor, QPalette, QFont, QIcon, QPixmap
from PyQt5.QtWidgets import QMessageBox


# Add these imports after the existing ones in File 2
import urllib.request
import urllib.error
import re
import os
from urllib.parse import urlparse, urljoin
from PyQt5.QtWidgets import QInputDialog, QLineEdit, QProgressBar

# Import for PDF generation (optional)
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# Import requests for advanced HTTP features
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# DeepSeek API integration
try:
    from openai import OpenAI
    DEEPSEEK_AVAILABLE = True
except ImportError:
    DEEPSEEK_AVAILABLE = False

class IPFetcher(QThread):
    ip_data_ready = pyqtSignal(dict)
    
    def run(self):
        try:
            # Get public IP using the exact command you specified
            public_ip = subprocess.run(
                ["powershell", "-Command", "Invoke-RestMethod -Uri https://api.ipify.org"],
                capture_output=True, text=True, timeout=10
            ).stdout.strip()
            
            # Get private IP
            hostname = socket.gethostname()
            private_ip = socket.getaddrinfo(hostname, None, socket.AF_INET)[0][4][0]
            
            # Get geolocation data for public IP
            geo_data = {}
            try:
                with urllib.request.urlopen(f"https://ipapi.co/{public_ip}/json/", timeout=5) as response:
                    geo_data = json.loads(response.read().decode())
            except:
                try:
                    with urllib.request.urlopen(f"https://ipinfo.io/{public_ip}/json", timeout=5) as response:
                        geo_data = json.loads(response.read().decode())
                except:
                    pass
            
            data = {
                'public_ip': public_ip,
                'private_ip': private_ip,
                'city': geo_data.get('city', 'Unknown'),
                'region': geo_data.get('region', geo_data.get('region_name', 'Unknown')),
                'country': geo_data.get('country_name', geo_data.get('country', 'Unknown')),
                'latitude': geo_data.get('latitude', 0.0),
                'longitude': geo_data.get('longitude', 0.0),
                'org': geo_data.get('org', geo_data.get('asn', 'Unknown')),
                'timezone': geo_data.get('timezone', 'Unknown')
            }
            
            self.ip_data_ready.emit(data)
        except Exception as e:
            self.ip_data_ready.emit({
                'public_ip': 'Error',
                'private_ip': 'Error',
                'city': 'Unknown',
                'region': 'Unknown',
                'country': 'Unknown',
                'latitude': 36.8820,
                'longitude': -97.3411,
                'org': 'Unknown',
                'timezone': 'Unknown',
                'error': str(e)
            })
            

class UserAgentRotator:
    """Advanced User-Agent rotator"""
    
    @staticmethod
    def get_random_ua():
        browser_name = random.choice(['Mozilla', 'Chrome', 'Safari', 'Firefox', 'Edge'])
        
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
        else:
            # Default common paths if file doesn't exist
            self.common_paths = [
                'admin', 'administrator', 'wp-admin', 'wp-login.php',
                'admin.php', 'admin/login', 'admin/login.php',
                'administrator/index.php', 'admin/index.php',
                'login', 'login.php', 'admin.html', 'panel',
                'cpanel', 'controlpanel', 'adminpanel',
                'moderator', 'webadmin', 'siteadmin'
            ]
        
        # CMS-specific wordlists
        self.cms_wordlists = {}
        cms_files = ['wordpress.txt', 'joomla.txt', 'laravel.txt', 'drupal.txt']
        for cms_file in cms_files:
            filepath = f'cms_paths/{cms_file}'
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
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
        self.log_signal.emit('CRAWLER', 'Scanning for hidden paths in robots.txt, sitemap.xml...', 'info')
        
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
        """Check for security headers"""
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
        self.setWindowTitle("EARTH COORDINATES - TERMINAL SIMULATION")
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("background-color: #0a0f14;")
        
        # Scanner thread reference
        self.scanner = None
        
        
        
        # Custom window frame but keep native controls
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
        
        # Add scan controls to terminal (call this method)
        self.add_scan_controls()
    
    def create_title_bar(self):
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
        self.title_label = QLabel("EARTH COORDINATES // ADMIN PANEL HUNTER")
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
        
        # Minimize button
        self.btn_minimize = QPushButton("−")
        self.btn_minimize.setStyleSheet(btn_style)
        self.btn_minimize.setToolTip("Minimize")
        self.btn_minimize.clicked.connect(self.showMinimized)
        title_layout.addWidget(self.btn_minimize)
        
    
        # Close button
        self.btn_close = QPushButton("×")
        self.btn_close.setStyleSheet(close_btn_style)
        self.btn_close.setToolTip("Close")
        self.btn_close.clicked.connect(self.close)
        title_layout.addWidget(self.btn_close)
        
        self.root_layout.addWidget(self.title_bar)
        
        # Enable dragging from title bar
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
    
    def fade_in(self):
        self.setWindowOpacity(0)
        self.animation = QPropertyAnimation(self, b"windowOpacity")
        self.animation.setDuration(1000)
        self.animation.setStartValue(0)
        self.animation.setEndValue(1)
        self.animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.animation.start()
    
    def create_sidebar(self):
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
        
        # Title
        title = QLabel("EARTH COORDINATES")
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
        
        # Realistic Earth visualization with NASA-style satellite imagery
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
            background: #0a0f14;;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            overflow: hidden;
        }
        
        .earth-system {
            position: relative;
            width: 340px;
            height: 340px;
        }
        
        .earth-container {
            position: relative;
            width: 300px;
            height: 300px;
            margin: 20px;
        }
        
        /* The Earth sphere */
        .earth {
            width: 300px;
            height: 300px;
            border-radius: 50%;
            position: relative;
            overflow: hidden;
            background: #0a1a2a;
            box-shadow: 
                inset -40px -40px 100px rgba(0, 0, 0, 0.9),
                inset 20px 20px 60px rgba(255, 255, 255, 0.2),
                0 0 60px rgba(74, 222, 128, 0.3),
                0 0 100px rgba(74, 222, 128, 0.1);
        }
        
        /* Earth images for each continent - using reliable NASA/visibleearth sources */
        .earth-texture {
            position: absolute;
            width: 300px;
            height: 300px;
            left: 0;
            top: 0;
            background-size: cover;
            background-position: center;
            border-radius: 50%;
            display: none;
        }
        
        /* North America */
        .earth-na {
            background-image: url('https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57752/land_shallow_topo_2048.jpg');
            display: none;
            animation: rotateEarth 25s linear infinite;
        }
        
        /* South America */
        .earth-sa {
            background-image: url('https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74092/world.200407.3x5400x2700.jpg');
            background-position: 30% center;
            display: none;
            animation: rotateEarth 25s linear infinite;
        }
        
        /* Africa - centered on Africa */
        .earth-africa {
            background-image: url('https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74092/world.200407.3x5400x2700.jpg');
            background-position: 50% center;
            display: none;
        
        }
        
        /* Asia */
        .earth-asia {
            background-image: url('https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74092/world.200407.3x5400x2700.jpg');
            background-position: 70% center;
            display: none;
            animation: rotateEarth 25s linear infinite;
        }
        
        /* Europe */
        .earth-europe {
            background-image: url('https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74092/world.200407.3x5400x2700.jpg');
            background-position: 55% 30%;
            display: none;
            animation: rotateEarth 25s linear infinite;
        }
        
        /* Australia */
        .earth-australia {
            background-image: url('https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74092/world.200407.3x5400x2700.jpg');
            background-position: 85% 70%;
            display: none;
            animation: rotateEarth 25s linear infinite;
        }
        
        /* Default - full world map rotating */
        .earth-default {
            background-image: url('https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74092/world.200407.3x5400x2700.jpg');
            background-size: 200% 100%;
            background-position: 0 center;
            display: block;
            animation: rotateEarth 30s linear infinite;
        }
        
        @keyframes rotateEarth {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        
        /* CSS-generated Earth fallback (if images fail) */
        .earth-generated {
            display: none;
            width: 100%;
            height: 100%;
            border-radius: 50%;
            background: 
                /* Oceans */
                radial-gradient(circle at 50% 50%, #1e4d6b 0%, #0d2f4a 100%),
                /* Continents - simplified shapes using gradients */
                radial-gradient(ellipse 80px 100px at 25% 30%, #4a6741 0%, transparent 100%),
                radial-gradient(ellipse 60px 120px at 30% 70%, #3d5a36 0%, transparent 100%),
                radial-gradient(ellipse 100px 140px at 50% 45%, #8b7355 0%, #5a4a3a 50%, transparent 100%),
                radial-gradient(ellipse 120px 100px at 70% 25%, #5a7d4a 0%, transparent 100%),
                radial-gradient(ellipse 80px 60px at 75% 75%, #a08050 0%, transparent 100%);
            position: absolute;
            top: 0;
            left: 0;
        }
        
        /* Night shadow overlay for 3D effect */
        .night-shadow {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border-radius: 50%;
            background: linear-gradient(135deg, 
                rgba(255,255,255,0.1) 0%, 
                rgba(255,255,255,0) 20%,
                rgba(0,0,0,0) 50%,
                rgba(0,0,0,0.5) 80%,
                rgba(0,0,0,0.9) 100%);
            z-index: 10;
            pointer-events: none;
        }
        
        /* Atmosphere glow */
        .atmosphere {
            position: absolute;
            top: -15px;
            left: -15px;
            right: -15px;
            bottom: -15px;
            border-radius: 50%;
            background: radial-gradient(circle at 50% 50%, 
                transparent 65%, 
                rgba(100,200,255,0.2) 75%, 
                rgba(74,222,128,0.15) 85%, 
                transparent 100%);
            animation: atmospherePulse 4s ease-in-out infinite;
            z-index: 5;
        }
        
        /* Satellite rings */
        .ring {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            border: 1px solid rgba(74, 222, 128, 0.2);
            border-radius: 50%;
        }
        
        .ring:nth-child(1) { width: 340px; height: 340px; animation: ringPulse 3s ease-in-out infinite; }
        .ring:nth-child(2) { width: 360px; height: 360px; animation: ringPulse 3s ease-in-out infinite 0.5s; }
        .ring:nth-child(3) { width: 380px; height: 380px; animation: ringPulse 3s ease-in-out infinite 1s; }
        
        /* LOCATION MARKER - Will be positioned dynamically */
        .location-marker {
            position: absolute;
            z-index: 100;
            /* Default center, will be overridden by JS */
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            display: block;
        }
        
        .marker-pulse {
            width: 20px;
            height: 20px;
            background: radial-gradient(circle, #ff3333 0%, #cc0000 70%, #990000 100%);
            border-radius: 50%;
            border: 3px solid rgba(255, 51, 51, 0.8);
            box-shadow: 
                0 0 0 10px rgba(255, 51, 51, 0.4),
                0 0 0 20px rgba(255, 51, 51, 0.2),
                0 0 0 30px rgba(255, 51, 51, 0.1),
                0 0 50px rgba(255, 51, 51, 1);
            animation: markerPulse 1.5s ease-in-out infinite;
        }
        
        .marker-ring {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 40px;
            height: 40px;
            border: 2px solid rgba(255, 51, 51, 0.6);
            border-radius: 50%;
            animation: markerRing 2s ease-out infinite;
        }
        
        .marker-ring:nth-child(3) {
            width: 60px;
            height: 60px;
            animation-delay: 0.6s;
            border-color: rgba(255, 51, 51, 0.4);
        }
        
        .marker-label {
            position: absolute;
            top: -35px;
            left: 50%;
            transform: translateX(-50%);
            color: #ff4444;
            font-family: 'Courier New', monospace;
            font-size: 14px;
            font-weight: bold;
            text-shadow: 
                0 0 10px rgba(255, 68, 68, 1),
                0 0 20px rgba(255, 68, 68, 0.8);
            white-space: nowrap;
            letter-spacing: 2px;
            background: rgba(0, 0, 0, 0.7);
            padding: 3px 10px;
            border-radius: 3px;
            border: 1px solid rgba(255, 68, 68, 0.5);
        }
        
        /* Scan line */
        .scan-line {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 2px;
            background: linear-gradient(90deg, 
                transparent, 
                rgba(74, 222, 128, 0.6) 20%, 
                rgba(74, 222, 128, 1) 50%, 
                rgba(74, 222, 128, 0.6) 80%, 
                transparent);
            box-shadow: 0 0 15px rgba(74, 222, 128, 1);
            animation: scan 3s ease-in-out infinite;
            z-index: 15;
        }
        
        /* Error message */
        .error-msg {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #4ade80;
            font-family: 'Courier New', monospace;
            font-size: 12px;
            text-align: center;
            z-index: 100;
            display: none;
        }
        
        @keyframes atmospherePulse {
            0%, 100% { opacity: 0.7; transform: scale(1); }
            50% { opacity: 1; transform: scale(1.02); }
        }
        
        @keyframes ringPulse {
            0%, 100% { opacity: 0.2; transform: translate(-50%, -50%) scale(1); }
            50% { opacity: 0.5; transform: translate(-50%, -50%) scale(1.01); }
        }
        
        @keyframes markerPulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.2); }
        }
        
        @keyframes markerRing {
            0% { transform: translate(-50%, -50%) scale(0.5); opacity: 1; }
            100% { transform: translate(-50%, -50%) scale(2.5); opacity: 0; }
        }
        
        @keyframes scan {
            0% { top: 0; opacity: 0; }
            10% { opacity: 1; }
            90% { opacity: 1; }
            100% { top: 100%; opacity: 0; }
        }
    </style>
</head>
<body>
    <div class="earth-system">
        <div class="ring"></div>
        <div class="ring"></div>
        <div class="ring"></div>
        <div class="earth-container">
            <div class="atmosphere"></div>
            <div class="earth" id="earthSphere">
                <!-- All continent images -->
                <div class="earth-texture earth-default" id="earthDefault"></div>
                <div class="earth-texture earth-na" id="earthNA"></div>
                <div class="earth-texture earth-sa" id="earthSA"></div>
                <div class="earth-texture earth-africa" id="earthAfrica"></div>
                <div class="earth-texture earth-asia" id="earthAsia"></div>
                <div class="earth-texture earth-europe" id="earthEurope"></div>
                <div class="earth-texture earth-australia" id="earthAustralia"></div>
                
                <!-- CSS-generated fallback -->
                <div class="earth-generated" id="earthGenerated"></div>
                
                <div class="night-shadow"></div>
                <div class="scan-line"></div>
                <div class="error-msg" id="errorMsg">LOADING...</div>
            </div>
            <div class="location-marker" id="locationMarker">
                <div class="marker-label" id="markerLabel">TARGET</div>
                <div class="marker-pulse"></div>
                <div class="marker-ring"></div>
                <div class="marker-ring"></div>
            </div>
        </div>
    </div>
    
    <script>
        // Check if images loaded successfully
        let imagesLoaded = 0;
        let imagesFailed = 0;
        const totalImages = 7;
        
        function checkAllImages() {
            if (imagesFailed >= 3) {
                // Too many failures, use CSS-generated Earth
                console.log('Using CSS-generated Earth fallback');
                document.querySelectorAll('.earth-texture').forEach(e => e.style.display = 'none');
                document.getElementById('earthGenerated').style.display = 'block';
                document.getElementById('errorMsg').style.display = 'none';
            }
        }
        
        // Preload images to check availability
        const imageUrls = [
            'https://eoimages.gsfc.nasa.gov/images/imagerecords/74000/74092/world.200407.3x5400x2700.jpg',
            'https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57752/land_shallow_topo_2048.jpg'
        ];
        
        imageUrls.forEach(url => {
            const img = new Image();
            img.onload = () => {
                imagesLoaded++;
                console.log('Image loaded:', url);
            };
            img.onerror = () => {
                imagesFailed++;
                console.log('Image failed:', url);
                checkAllImages();
            };
            img.src = url;
        });
        
        // Global function to show specific continent
        window.showContinent = function(continent) {
            console.log('Showing continent:', continent);
            
            // Hide all earth textures and stop their animations
            const allEarths = document.querySelectorAll('.earth-texture');
            allEarths.forEach(e => {
                e.style.display = 'none';
                e.style.animation = 'none';
            });
            
            // Hide generated fallback
            const generated = document.getElementById('earthGenerated');
            if (generated) generated.style.display = 'none';
            
            // Get marker element
            const marker = document.getElementById('locationMarker');
            const label = document.getElementById('markerLabel');
            
            // Default center position
            let markerTop = 50;
            let markerLeft = 50;
            let targetId = 'earthDefault';
            let labelText = 'TARGET';
            
            switch(continent.toLowerCase()) {
                case 'north_america':
                case 'n.america':
                case 'na':
                    targetId = 'earthNA';
                    labelText = 'N.AMERICA';
                    markerTop = 35;
                    markerLeft = 25;
                    break;
                case 'south_america':
                case 's.america':
                case 'sa':
                    targetId = 'earthSA';
                    labelText = 'S.AMERICA';
                    markerTop = 70;
                    markerLeft = 30;
                    break;
                case 'africa':
                    targetId = 'earthAfrica';
                    labelText = 'AFRICA';
                    // Center of Africa - moved more to the right and slightly up
                    markerTop = 50;  // Vertical center
                    markerLeft = 70; // Moved right to center on Africa
                    break;
                case 'asia':
                    targetId = 'earthAsia';
                    labelText = 'ASIA';
                    markerTop = 40;
                    markerLeft = 75;
                    break;
                case 'europe':
                    targetId = 'earthEurope';
                    labelText = 'EUROPE';
                    markerTop = 30;
                    markerLeft = 55;
                    break;
                case 'australia':
                case 'oceania':
                    targetId = 'earthAustralia';
                    labelText = 'AUSTRALIA';
                    markerTop = 75;
                    markerLeft = 85;
                    break;
                default:
                    targetId = 'earthDefault';
                    labelText = continent.toUpperCase();
                    markerTop = 50;
                    markerLeft = 50;
            }
            
            // Position the marker
            if (marker) {
                marker.style.top = markerTop + '%';
                marker.style.left = markerLeft + '%';
                marker.style.display = 'block';
                console.log('Marker positioned at:', markerTop + '%', markerLeft + '%');
            }
            
            // Show the selected continent
            const target = document.getElementById(targetId);
            if (target) {
                target.style.display = 'block';
                if (targetId !== 'earthDefault') {
                    target.style.animation = 'none';
                    target.style.transform = 'none';
                }
                console.log('Showing element:', targetId);
            } else {
                console.log('Element not found:', targetId);
                document.getElementById('earthDefault').style.display = 'block';
            }
            
            // Update label
            if (label) {
                label.textContent = labelText;
            }
        };
        
        // Legacy function for backwards compatibility
        window.updateMarkerPosition = function(lat, lon) {
            console.log('Coordinates received:', lat, lon);
            
            // Determine continent from coordinates
            let continent = 'default';
            
            if (lat > 15 && lat < 70 && lon > -130 && lon < -60) {
                continent = 'north_america';
            } else if (lat > -55 && lat < 15 && lon > -85 && lon < -35) {
                continent = 'south_america';
            } else if (lat > -35 && lat < 35 && lon > -20 && lon < 55) {
                continent = 'africa';
            } else if (lat > 10 && lat < 70 && lon > 55 && lon < 140) {
                continent = 'asia';
            } else if (lat > 35 && lat < 70 && lon > -10 && lon < 40) {
                continent = 'europe';
            } else if (lat > -50 && lat < -10 && lon > 110 && lon < 180) {
                continent = 'australia';
            }
            
            console.log('Detected continent:', continent);
            window.showContinent(continent);
        };
        
        // Initialize with Africa for testing (remove in production)
        // setTimeout(() => window.showContinent('africa'), 1000);
    </script>
</body>
</html>
"""
        
        self.earth_view.setHtml(earth_html)
        sidebar_layout.addWidget(self.earth_view, alignment=Qt.AlignCenter)
        
        # Coordinates display
        self.coords_label = QLabel("36.88200° N    -97.34110° W")
        self.coords_label.setStyleSheet("""
            color: #d1d5db;
            font-family: 'Courier New', monospace;
            font-size: 16px;
            font-weight: bold;
            text-align: center;
            padding: 12px;
            background: rgba(74, 222, 128, 0.05);
            border: 1px solid #1a3d2e;
            border-radius: 4px;
            margin-top: 10px;
        """)
        self.coords_label.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(self.coords_label)
        
        # Data readout labels
        self.data_labels = {}
        data_items = ['LATITUDE', 'LONGITUDE']
        
        for item in data_items:
            container = QFrame()
            container.setStyleSheet("""
                QFrame {
                    background: rgba(74, 222, 128, 0.03);
                    border-left: 3px solid #4ade80;
                    padding: 8px;
                    margin: 5px 0;
                }
            """)
            container_layout = QVBoxLayout(container)
            container_layout.setSpacing(2)
            container_layout.setContentsMargins(10, 5, 10, 5)
            
            header = QLabel(item)
            header.setStyleSheet("""
                color: #d1d5db;
                font-family: 'Courier New', monospace;
                font-size: 10px;
                letter-spacing: 2px;
            """)
            
            value = QLabel("---")
            value.setStyleSheet("""
                color: #86efac;
                font-family: 'Courier New', monospace;
                font-size: 14px;
                font-weight: bold;
            """)
            value.setObjectName(f"{item.lower()}_value")
            self.data_labels[item] = value
            
            container_layout.addWidget(header)
            container_layout.addWidget(value)
            sidebar_layout.addWidget(container)
        
        sidebar_layout.addStretch()
        self.content_layout.addWidget(self.sidebar)
    
    def create_terminal(self):
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
        header = QLabel("[TERMINAL] — DATA STREAM: OAK_410")
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
        
        # Terminal output area using WebEngine for authentic terminal look
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
                
                .cursor {
                    display: inline-block;
                    width: 8px;
                    height: 15px;
                    background: #4ade80;
                    animation: blink 1s step-end infinite;
                    margin-left: 5px;
                    vertical-align: middle;
                }
                
                @keyframes blink {
                    50% { opacity: 0; }
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
                
                .status-item {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                
                .status-indicator {
                    width: 8px;
                    height: 8px;
                    border-radius: 50%;
                    background: #4ade80;
                    animation: pulse 2s ease-in-out infinite;
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
                <div class="status-item">
                    <span class="status-indicator"></span>
                    <span>SYSTEM: ONLINE</span>
                </div>
                <div class="status-item">
                    <span>ENCRYPTION: AES-256-GCM</span>
                </div>
                <div class="status-item">
                    <span>UPLINK: ESTABLISHED</span>
                </div>
            </div>
            <script>
                function addLogEntry(timestamp, category, message, type = 'normal') {
                    const container = document.getElementById('log-container');
                    const entry = document.createElement('div');
                    entry.className = 'log-entry';
                    
                    const typeClass = type === 'error' ? 'error' : 
                                    type === 'warning' ? 'warning' : 
                                    type === 'info' ? 'info' : 
                                    type === 'success' ? 'success' : '';
                    
                    entry.innerHTML = `
                        <span class="timestamp">${timestamp}</span>
                        <span class="category">[${category}]</span>
                        <span class="message ${typeClass}">${message}</span>
                    `;
                    
                    container.appendChild(entry);
                    
                    // Keep only last 100 entries (increased from 50 for better history)
                    while (container.children.length > 100) {
                        container.removeChild(container.firstChild);
                    }
                    
                    // REMOVED: Auto-scroll disabled - user can scroll manually
                    // window.scrollTo(0, document.body.scrollHeight);
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
        
        # IP Info Panel at bottom
        self.ip_panel = QFrame()
        self.ip_panel.setStyleSheet("""
            QFrame {
                background: #0d1218;
                border: 1px solid #1a3d2e;
                border-radius: 4px;
                margin-top: 10px;
            }
        """)
        
        ip_layout = QVBoxLayout(self.ip_panel)
        ip_layout.setSpacing(8)
        ip_layout.setContentsMargins(15, 15, 15, 15)
        
        # IP Info header
        ip_header = QLabel("▼ NETWORK INTELLIGENCE // GEOLOCATION DATA")
        ip_header.setStyleSheet("""
            color: #2563eb;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 1px;
            margin-bottom: 5px;
        """)
        ip_layout.addWidget(ip_header)
        
        # IP data grid
        ip_grid = QHBoxLayout()
        
        self.ip_displays = {}
        ip_fields = [
            ('PUBLIC_IP', 'Public IP'),
            ('PRIVATE_IP', 'Private IP'),
            ('LOCATION', 'Location'),
            ('COORDINATES', 'Coordinates'),
            ('ISP', 'ISP/Organization')
        ]
        
        for key, label in ip_fields:
            container = QVBoxLayout()
            
            lbl = QLabel(label)
            lbl.setStyleSheet("""
                color: #22c55e;
                font-family: 'Courier New', monospace;
                font-size: 9px;
                letter-spacing: 1px;
            """)
            
            val = QLabel("SCANNING...")
            val.setStyleSheet("""
                color: #d1d5db;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                font-weight: bold;
                padding: 5px;
                background: rgba(74, 222, 128, 0.05);
                border-radius: 3px;
            """)
            val.setObjectName(f"ip_{key}")
            self.ip_displays[key] = val
            
            container.addWidget(lbl)
            container.addWidget(val)
            ip_grid.addLayout(container)
        
        ip_layout.addLayout(ip_grid)
        terminal_layout.addWidget(self.ip_panel)
        
        self.content_layout.addWidget(self.terminal, stretch=1)
    
    def update_ip_data(self, data):
        # Extract coordinates with fallback
        lat = data.get('latitude') or 0.0
        lon = data.get('longitude') or 0.0
        
        # If coordinates are 0, try to get from ipinfo as fallback
        if lat == 0.0 and lon == 0.0 and data.get('public_ip') not in ['Error', 'Unknown']:
            try:
                result = subprocess.run(
                    ["powershell", "-Command", f"Invoke-RestMethod -Uri https://ipinfo.io/{data.get('public_ip')}/json"],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    import json
                    ipinfo_data = json.loads(result.stdout)
                    loc = ipinfo_data.get('loc', '0,0').split(',')
                    if len(loc) == 2:
                        lat = float(loc[0])
                        lon = float(loc[1])
            except Exception as e:
                print(f"Fallback geolocation failed: {e}")
        
        # If still 0, use default coordinates (Oklahoma)
        if lat == 0.0 and lon == 0.0:
            lat = 36.8820
            lon = -97.3411
        
        # Update sidebar coordinates display
        lon_abs = abs(lon)
        lon_dir = 'W' if lon < 0 else 'E'
        self.coords_label.setText(f"{lat:.5f}° N    {lon_abs:.5f}° {lon_dir}")
        self.data_labels['LATITUDE'].setText(f"{lat:.5f}°")
        self.data_labels['LONGITUDE'].setText(f"{lon:.5f}°")
        
        # Update IP panel
        self.ip_displays['PUBLIC_IP'].setText(data.get('public_ip', 'Unknown'))
        self.ip_displays['PRIVATE_IP'].setText(data.get('private_ip', 'Unknown'))
        
        location = f"{data.get('city', 'Unknown')}, {data.get('region', 'Unknown')}, {data.get('country', 'Unknown')}"
        self.ip_displays['LOCATION'].setText(location)
        
        coords = f"{lat:.4f}, {lon:.4f}"
        self.ip_displays['COORDINATES'].setText(coords)
        
        self.ip_displays['ISP'].setText(data.get('org', 'Unknown')[:25])
        
        # SHOW CORRECT CONTINENT BASED ON COORDINATES
        def update_continent():
            # Simple direct call to JavaScript function
            js = f"""
            (function() {{
                var lat = {lat};
                var lon = {lon};
                var continent = 'default';
                
                if (lat > 15 && lat < 70 && lon > -130 && lon < -60) continent = 'north_america';
                else if (lat > -55 && lat < 15 && lon > -85 && lon < -35) continent = 'south_america';
                else if (lat > -35 && lat < 35 && lon > -20 && lon < 55) continent = 'africa';
                else if (lat > 10 && lat < 70 && lon > 55 && lon < 140) continent = 'asia';
                else if (lat > 35 && lat < 70 && lon > -10 && lon < 40) continent = 'europe';
                else if (lat > -50 && lat < -10 && lon > 110 && lon < 180) continent = 'australia';
                
                console.log('Python calling showContinent with:', continent);
                if (typeof showContinent === 'function') {{
                    showContinent(continent);
                }} else {{
                    console.error('showContinent function not found');
                }}
            }})();
            """
            self.earth_view.page().runJavaScript(js)
        
        # Try multiple times with increasing delays
        QTimer.singleShot(500, update_continent)
        QTimer.singleShot(1500, update_continent)
        QTimer.singleShot(3000, update_continent)
        
        # Add log entries
        self.log_entries.extend([
            ('NETWORK', f'Public IP resolved: {data.get("public_ip", "Unknown")}', 'success'),
            ('NETWORK', f'Private IP resolved: {data.get("private_ip", "Unknown")}', 'success'),
            ('GEOLOC', f'Location identified: {location}', 'info'),
            ('COORD', f'Lat/Long locked: {coords}', 'success'),
        ])
    
    def add_log_entry(self):
        # Only show real log entries, no demo/random data
        if self.current_log_index < len(self.log_entries):
            cat, msg, typ = self.log_entries[self.current_log_index]
            self.current_log_index += 1
            
            now = datetime.utcnow()
            timestamp = now.strftime('%H:%M:%S GMT')
            
            js_code = f"addLogEntry('{timestamp}', '{cat}', '{msg}', '{typ}');"
            self.terminal_view.page().runJavaScript(js_code)
        # else: do nothing - no more fake demo entries
            
        
    
    def add_scan_controls(self):
        """Add scan control buttons to the terminal area - adds to existing terminal layout"""
        # Find the terminal layout (it's the layout of self.terminal)
        terminal_layout = self.terminal.layout()
        
        # Update the terminal header text
        # We need to find the header label and update it
        for i in range(terminal_layout.count()):
            widget = terminal_layout.itemAt(i).widget()
            if isinstance(widget, QLabel) and "TERMINAL" in widget.text():
                widget.setText("[ADMIN PANEL HUNTER] — AI-POWERED SECURITY SCANNER")
                break
        
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
            QPushButton:disabled {
                background-color: #1a3d2e;
                color: #6b7280;
                border-color: #374151;
            }
        """)
        self.scan_btn.clicked.connect(self.start_scan)
        control_layout.addWidget(self.scan_btn)
        
        # API Key button
        self.api_btn = QPushButton("🔑 SET API KEY")
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
        
        # Add control frame to terminal layout
        terminal_layout.addWidget(control_frame)
    
    def set_api_key(self):
        """Prompt user for DeepSeek API key"""
        dialog = QInputDialog(self)
        dialog.setWindowTitle('DeepSeek API Key')
        dialog.setLabelText('Enter your DeepSeek API Key:\n(Get from https://platform.deepseek.com/)')
        dialog.setTextEchoMode(QLineEdit.Password)
        
        # FIXED: Proper styling with terminal theme colors
        dialog.setStyleSheet("""
            QInputDialog {
                background-color: #0d1218;
                border: 2px solid #1a3d2e;
            }
            QLabel {
                color: #4ade80;
                background-color: transparent;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                padding: 10px;
            }
            QLineEdit {
                background-color: #0a0f14;
                color: #4ade80;
                border: 2px solid #4ade80;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                selection-background-color: #4ade80;
                selection-color: #0a0f14;
            }
            QPushButton {
                background-color: #1a3d2e;
                color: #4ade80;
                border: 1px solid #4ade80;
                border-radius: 4px;
                padding: 8px 20px;
                font-family: 'Courier New', monospace;
                font-weight: bold;
                min-width: 80px;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #2a5d4e;
                color: #86efac;
                border-color: #86efac;
            }
        """)
        
        # FIXED: Use exec_() instead of getText() static method
        ok = dialog.exec_()
        if ok:
            key = dialog.textValue()
            if key:
                self.deepseek_api_key = key
                self.add_terminal_log('API', 'DeepSeek API key configured successfully', 'success')

    def start_scan(self):
        """Start the admin panel scan"""
        target_dialog = QInputDialog(self)
        target_dialog.setWindowTitle('Target Website')
        target_dialog.setLabelText('Enter target website URL:\n(ex: example.com or https://example.com)')
        
        # FIXED: Matching terminal theme styling
        target_dialog.setStyleSheet("""
            QInputDialog {
                background-color: #0d1218;
                border: 2px solid #1a3d2e;
            }
            QLabel {
                color: #4ade80;
                background-color: transparent;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                padding: 10px;
            }
            QLineEdit {
                background-color: #0a0f14;
                color: #4ade80;
                border: 2px solid #4ade80;
                border-radius: 4px;
                padding: 8px;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                selection-background-color: #4ade80;
                selection-color: #0a0f14;
            }
            QPushButton {
                background-color: #1a3d2e;
                color: #4ade80;
                border: 1px solid #4ade80;
                border-radius: 4px;
                padding: 8px 20px;
                font-family: 'Courier New', monospace;
                font-weight: bold;
                min-width: 80px;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #2a5d4e;
                color: #86efac;
            }
        """)
        
        # FIXED: Use exec_() to show the styled dialog
        ok = target_dialog.exec_()
        if not ok:
            return
        target = target_dialog.textValue()
        if not target:
            return
        
        if not hasattr(self, 'deepseek_api_key') or not self.deepseek_api_key:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('No API Key')
            msg_box.setText('No DeepSeek API key set. Continue with fallback detection?\n\nClick Yes to continue without AI, or No to set API key first.')
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.No)
            
            # FIXED: Better styling for QMessageBox
            msg_box.setStyleSheet("""
                QMessageBox {
                    background-color: #0d1218;
                    border: 2px solid #1a3d2e;
                }
                QMessageBox QLabel {
                    color: #4ade80;
                    background-color: transparent;
                    font-family: 'Courier New', monospace;
                    font-size: 12px;
                    padding: 15px;
                    min-width: 400px;
                }
                QMessageBox QPushButton {
                    background-color: #1a3d2e;
                    color: #4ade80;
                    border: 1px solid #4ade80;
                    border-radius: 4px;
                    padding: 8px 20px;
                    font-family: 'Courier New', monospace;
                    font-weight: bold;
                    min-width: 80px;
                    margin: 5px;
                }
                QMessageBox QPushButton:hover {
                    background-color: #2a5d4e;
                    color: #86efac;
                }
            """)
            
            reply = msg_box.exec()
            if reply == QMessageBox.No:
                return
        
        # Clear previous logs
        self.clear_terminal_logs()
        
        # Show progress bar
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Create and start scanner thread
        self.scanner = AdminPanelScanner(target, self.deepseek_api_key if hasattr(self, 'deepseek_api_key') else None)
        self.scanner.log_signal.connect(self.add_terminal_log)
        self.scanner.progress_signal.connect(self.progress_bar.setValue)
        self.scanner.found_panel_signal.connect(self.on_panel_found)
        self.scanner.scan_complete_signal.connect(self.on_scan_complete)
        self.scanner.start()
        
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("SCANNING...")
    
    def on_panel_found(self, url, details):
        """Handle found panel - flash the marker"""
        js_code = """
        (function() {
            var marker = document.getElementById('locationMarker');
            var label = document.getElementById('markerLabel');
            if (marker && label) {
                var originalText = label.textContent;
                var originalColor = label.style.color;
                label.textContent = 'PANEL FOUND';
                label.style.color = '#ff4444';
                setTimeout(function() {
                    label.textContent = originalText;
                    label.style.color = originalColor;
                }, 2000);
            }
        })();
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
        """Add log to terminal view - use existing terminal_view"""
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
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    font = QFont('Courier New', 10)
    font.setStyleHint(QFont.Monospace)
    app.setFont(font)
    
    window = SatelliteTerminal()
    window.show()
    sys.exit(app.exec_())