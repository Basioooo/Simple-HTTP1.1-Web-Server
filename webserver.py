import socket
import os
import threading
import mimetypes
from datetime import datetime
import json
import time

class SimpleHTTPServer:
    def __init__(self, host='localhost', port=8080):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.running = False

    def start(self):
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        print(f"Server started on http://{self.host}:{self.port}")
        print(f"To shutdown the server, visit: http://{self.host}:{self.port}/shutdown")
        try:
            while self.running:
                client_socket, client_address = self.server_socket.accept()
                print(f"Connection from {client_address}")
                thread = threading.Thread(target=self.handle_request, args=(client_socket,))
                thread.start()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            self.stop()
        except Exception as e:
            print(f"Server error: {e}")
            self.stop()

    def stop(self):
        self.running = False
        try:
            temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            temp_socket.connect((self.host, self.port))
            temp_socket.close()
        except:
            pass
        self.server_socket.close()
        print("Server has been stopped")

    def handle_request(self, client_socket):
        try:
            request_data = client_socket.recv(1024).decode('utf-8')
            if not request_data:
                return
            request_lines = request_data.split('\r\n')
            request_line = request_lines[0]
            method, path, _ = request_line.split(' ')
            
            if path == '/shutdown':
                self.handle_shutdown(client_socket)
                return
                
            if '../' in path:
                self.send_response(client_socket, 403, "Forbidden", self.generate_error_page(403, "Forbidden", "Access denied"))
                return
                
            if path == '/':
                path = '/index.html'
                
            if path == '/status':
                self.handle_status(client_socket)
                return
                
            file_path = os.path.join(self.base_dir, 'www', path.lstrip('/'))
            
            if method == 'GET':
                self.handle_get(client_socket, file_path)
            else:
                self.send_response(client_socket, 501, "Not Implemented", self.generate_error_page(501, "Not Implemented", "Method not supported"))
                
        except Exception as e:
            print(f"Error handling request: {e}")
            self.send_response(client_socket, 500, "Internal Server Error", "Server encountered an error")

    def handle_shutdown(self, client_socket):
        response_content = self.generate_page("Server Shutdown", """
            <div class="notification is-warning">
                <h1 class="title">Server is shutting down...</h1>
                <p>The web server is now stopping. Please wait a moment.</p>
            </div>
        """)
        self.send_response(
            client_socket,
            200,
            "OK",
            response_content,
            headers={
                'Content-Type': 'text/html',
                'Connection': 'close'
            }
        )
        threading.Thread(target=self.stop).start()

    def handle_get(self, client_socket, file_path):
        try:
            if os.path.isfile(file_path):
                with open(file_path, 'rb') as file:
                    content = file.read()
                
                mime_type, _ = mimetypes.guess_type(file_path)
                mime_type = mime_type or 'application/octet-stream'
                
                self.send_response(
                    client_socket,
                    200,
                    "OK",
                    content,
                    headers={
                        'Content-Type': mime_type,
                        'Content-Length': len(content)
                    }
                )
            else:
                # Simple 404 error without theme
                error_content = b"<html><body><h1>404 Not Found</h1><p>The requested resource was not found.</p></body></html>"
                self.send_response(
                    client_socket,
                    404,
                    "Not Found",
                    error_content,
                    headers={
                        'Content-Type': 'text/html',
                        'Content-Length': len(error_content)
                    }
                )
                
        except PermissionError:
            self.send_response(client_socket, 403, "Forbidden", self.generate_error_page(403, "Forbidden", "Access denied"))
        except Exception as e:
            print(f"Error serving file: {e}")
            self.send_response(client_socket, 500, "Internal Server Error", "Server error")

    def handle_status(self, client_socket):
        try:
            try:
                import psutil
                mem = psutil.virtual_memory()
                memory = f"{mem.percent}% ({mem.used // (1024*1024)}MB/{mem.total // (1024*1024)}MB)"
                cpu = f"{psutil.cpu_percent()}%"
                uptime = time.time() - psutil.boot_time()
                hours, rem = divmod(int(uptime), 3600)
                minutes, seconds = divmod(rem, 60)
                uptime_str = f"{hours}h {minutes}m {seconds}s"
            except ImportError:
                memory = "psutil not installed"
                cpu = "psutil not installed"
                uptime_str = "N/A"
            status = {
                "status": "Online",
                "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "uptime": uptime_str,
                "memory": memory,
                "cpu": cpu
            }
            content = json.dumps(status)
            self.send_response(
                client_socket,
                200,
                "OK",
                content,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': len(content)
                }
            )
        except Exception as e:
            error = json.dumps({"status": "Error", "error": str(e)})
            self.send_response(
                client_socket,
                500,
                "Internal Server Error",
                error,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': len(error)
                }
            )

    def send_response(self, client_socket, status_code, status_message, content, headers=None):
        if headers is None:
            headers = {}
        default_headers = {
            'Server': 'Team20WebServerHTTP/1.0',
            'Date': datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT'),
            'Connection': 'close'
        }
        response_headers = {**default_headers, **headers}
        response_lines = [
            f"HTTP/1.1 {status_code} {status_message}",
            *[f"{key}: {value}" for key, value in response_headers.items()]
        ]
        response_header = '\r\n'.join(response_lines) + '\r\n\r\n'
        client_socket.send(response_header.encode('utf-8'))
        if isinstance(content, str):
            content = content.encode('utf-8')
        if content:
            client_socket.send(content)

    def generate_page(self, title, content):
        return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.3/css/bulma.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        .hero {{
            background: linear-gradient(135deg, #6e48aa 0%, #9d50bb 100%);
        }}
        .card {{
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }}
        .card:hover {{
            transform: translateY(-5px);
        }}
        footer {{
            background-color: #f5f5f5;
            padding: 2rem 1.5rem;
        }}
    </style>
</head>
<body>
    <section class="hero is-medium is-bold">
        <div class="hero-body">
            <div class="container">
                <h1 class="title is-1 has-text-white">
                    <i class="fas fa-server"></i> Team 20 Web Server
                </h1>
                <h2 class="subtitle has-text-light">
                    Network Basics Project
                </h2>
            </div>
        </div>
    </section>

    <section class="section">
        <div class="container">
            {content}
        </div>
    </section>

    <footer class="footer">
        <div class="content has-text-centered">
            <p>
                <strong>Team 20 Web Server</strong>.
            </p>
        </div>
    </footer>
</body>
</html>
        """

    def generate_error_page(self, error_code, error_name, message):
        icons = {
            403: "fa-ban",
            404: "fa-exclamation-circle",
            500: "fa-server",
            501: "fa-code"
        }
        return self.generate_page(f"{error_code} {error_name}", f"""
            <div class="notification is-danger">
                <h1 class="title"><i class="fas {icons.get(error_code, 'fa-bug')}"></i> {error_code} {error_name}</h1>
                <p>{message}</p>
                <a href="/" class="button is-link mt-4">Return to Home</a>
            </div>
        """)

def main():
    www_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'www')
    if not os.path.exists(www_dir):
        os.makedirs(www_dir)
        print(f"Created 'www' directory at {www_dir}")
        
        # Create index.html
        with open(os.path.join(www_dir, 'index.html'), 'w') as f:
            f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>Team 20 Web Server</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.3/css/bulma.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        .hero {
            background: linear-gradient(135deg, #6e48aa 0%, #9d50bb 100%);
        }
        .card {
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }
        .card:hover {
            transform: translateY(-5px);
        }
        footer {
            background-color: #f5f5f5;
            padding: 2rem 1.5rem;
        }
    </style>
</head>
<body>
    <section class="hero is-medium is-bold">
        <div class="hero-body">
            <div class="container">
                <h1 class="title is-1 has-text-white">
                    <i class="fas fa-server"></i> Team 20 Web Server
                </h1>
                <h2 class="subtitle has-text-light">
                    Network Basics Project
                </h2>
            </div>
        </div>
    </section>

    <section class="section">
        <div class="container">
            <div class="columns">
                <div class="column">
                    <div class="card">
                        <div class="card-content">
                            <h3 class="title is-4"><i class="fas fa-home"></i> Welcome</h3>
                            <p>This is our HTTP web server.</p>
                            <a href="/about.html" class="button is-link mt-4">Learn More</a>
                        </div>
                    </div>
                </div>
                <div class="column">
                    <div class="card">
                        <div class="card-content">
                            <h3 class="title is-4"><i class="fas fa-bug"></i> Test 404</h3>
                            <p>Try accessing a non-existent page to see our custom 404 error page.</p>
                            <a href="/test.html" class="button is-info mt-4">Test 404</a>
                        </div>
                    </div>
                </div>
                <div class="column">
                    <div class="card">
                        <div class="card-content">
                            <h3 class="title is-4"><i class="fas fa-power-off"></i> Admin</h3>
                            <p>Server administration and control panel.</p>
                            <a href="/shutdown" class="button is-danger mt-4">Shutdown Server</a>
                        </div>
                    </div>
                </div>
            </div>
            <div class="columns mt-5">
                <div class="column">
                    <div class="card">
                        <div class="card-content">
                            <h3 class="title is-4"><i class="fas fa-file-code"></i> JSON Example</h3>
                            <p>Check out our sample JSON data file.</p>
                            <a href="/data.json" class="button is-primary mt-4">View JSON</a>
                        </div>
                    </div>
                </div>
                <div class="column">
                    <div class="card">
                        <div class="card-content">
                            <h3 class="title is-4"><i class="fas fa-image"></i> Image Example</h3>
                            <p>View a sample image served by the server.</p>
                            <a href="/sample.jpg" class="button is-success mt-4">View Image</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <footer class="footer">
        <div class="content has-text-centered">
            <p>
                <strong>Team 20 Web Server Project</strong>.
            </p>
        </div>
    </footer>
</body>
</html>
            """)
        
        # Create about.html
        with open(os.path.join(www_dir, 'about.html'), 'w') as f:
            f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>About Our Server</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bulma@0.9.3/css/bulma.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        .hero {
            background: linear-gradient(135deg, #6e48aa 0%, #9d50bb 100%);
        }
        .content-section {
            padding: 3rem 1.5rem;
        }
        footer {
            background-color: #f5f5f5;
            padding: 2rem 1.5rem;
        }
    </style>
</head>
<body>
    <section class="hero is-medium is-bold">
        <div class="hero-body">
            <div class="container">
                <h1 class="title is-1 has-text-white">
                    <i class="fas fa-info-circle"></i> About Our Server
                </h1>
                <h2 class="subtitle has-text-light">
                    Technical Details and Implementation
                </h2>
            </div>
        </div>
    </section>

    <section class="content-section">
        <div class="container">
            <div class="content">
                <h3 class="title is-3"><i class="fas fa-code"></i> Server Implementation</h3>
                <p>This web server was built using Python's socket library to handle HTTP requests at a low level. Key features include:</p>
                <ul>
                    <li>Multi-threaded request handling</li>
                    <li>Proper HTTP/1.1 response generation</li>
                    <li>MIME type detection for different file types</li>
                    <li>Custom error pages (404, 403, 500, etc.)</li>
                    <li>Security against directory traversal attacks</li>
                </ul>

                <h3 class="title is-3 mt-5"><i class="fas fa-cogs"></i> Technical Specifications</h3>
                <div class="box">
                    <article class="media">
                        <div class="media-content">
                            <div class="content">
                                <p>
                                    <strong>HTTP Version:</strong> 1.1<br>
                                    <strong>Supported Methods:</strong> GET<br>
                                    <strong>Default Port:</strong> 8080<br>
                                    <strong>Root Directory:</strong> /www<br>
                                    <strong>Error Handling:</strong> Custom HTML error pages<br>
                                    <strong>Security:</strong> Basic path traversal protection
                                </p>
                            </div>
                        </div>
                    </article>
                </div>

                <h3 class="title is-3 mt-5"><i class="fas fa-users"></i> Development Team</h3>
                <div class="columns">
                    <div class="column">
                        <div class="box">
                            <h4 class="title is-4">Team 20</h4>
                            <p>Network Basics Project</p>
                            <p>Supervisor: DR. Mariam Labib</p>
                        </div>
                    </div>
                </div>

                <a href="/" class="button is-link"><i class="fas fa-arrow-left"></i> Back to Home</a>
            </div>
        </div>
    </section>

    <footer class="footer">
        <div class="content has-text-centered">
            <p>
                <strong>Team 20 Web Server Project</strong>.
            </p>
        </div>
    </footer>
</body>
</html>
            """)
        
        # Create sample JSON file
        with open(os.path.join(www_dir, 'data.json'), 'w') as f:
            f.write("""
{
    "project": "Team 20 Web Server",
    "course": "Network Basics",
    "semester": "Spring 2025",
    "features": [
        "HTTP/1.1 compliant",
        "Multi-threaded",
        "JSON support",
        "Image support",
        "Custom error pages"
    ],
    "team_members": [
        "Mahmoud Hesham (240101375)",
        "Doaa Shahin (240100001)",
        "Malak Islam (240105935",
        "Sama Abd El-Wahhab (240102714)"
    ]
}
            """)
        
        print("Created sample files (index.html, about.html, data.json)")
        print("Note: To test image support, add an image file named 'sample.jpg' to the www directory")

    server = SimpleHTTPServer()
    server.start()

if __name__ == '__main__':
    main()