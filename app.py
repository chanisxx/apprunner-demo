from flask import Flask, jsonify
import logging
import os
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)

SECRET_KEY = os.getenv('SECRET_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is required")

app.config['SECRET_KEY'] = SECRET_KEY

# Create database engine with connection timeout
db_engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    connect_args={
        "connect_timeout": 10,
        "application_name": "flask_app_runner"
    }
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/')
def home():
    return     '''
    <h1>Flask App on AWS App Runner</h1>
    <p>Your Flask application is running successfully! June 24th</p>
    <p>Flask Version: 3.0.3</p>
    <p>Connected to custom VPC and RDS PostgreSQL</p>
    <a href="/internet-test">Connectivity test</a> | 
    <a href="/network-test">Test Network</a> |
    <a href="/db-test">Test Database</a> |
    '''

@app.route('/internet-test')
def internet_test():
    import socket
    import urllib.request
    
    results = {}
    
    # Test 1: DNS Resolution
    try:
        ip = socket.gethostbyname('google.com')
        results['dns_resolution'] = f"✅ Working: google.com → {ip}"
    except Exception as e:
        results['dns_resolution'] = f"❌ Failed: {str(e)}"
    
    # Test 2: Can we reach DNS servers?
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('8.8.8.8', 53))
        sock.close()
        results['dns_server_connectivity'] = "✅ Can reach 8.8.8.8:53" if result == 0 else "❌ Cannot reach DNS"
    except Exception as e:
        results['dns_server_connectivity'] = f"❌ Error: {str(e)}"
    
    # Test 3: HTTP connectivity to IP address (bypasses DNS)
    try:
        response = urllib.request.urlopen('http://142.250.191.14/', timeout=10)  # Google's IP
        results['http_by_ip'] = f"✅ HTTP to IP works: {response.status}"
    except Exception as e:
        results['http_by_ip'] = f"❌ Failed: {str(e)}"
    
    # Test 4: HTTPS by domain name
    try:
        response = urllib.request.urlopen('https://google.com', timeout=10)
        results['https_by_domain'] = f"✅ HTTPS works: {response.status}"
    except Exception as e:
        results['https_by_domain'] = f"❌ Failed: {str(e)}"
    
    # Test 5: Database connectivity (should work)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex(('flask-app-db-v2.c1k84uw8eeo3.us-east-2.rds.amazonaws.com', 5432))
        sock.close()
        results['database'] = "✅ Connected" if result == 0 else "❌ Failed"
    except Exception as e:
        results['database'] = f"❌ Error: {str(e)}"
    
    return results


@app.route('/network-test')
def network_test():
    """Test network connectivity without database"""
    import socket
    
    try:
        # Extract host and port from DATABASE_URL
        # postgresql://user:pass@host:port/db
        url_parts = DATABASE_URL.split('@')[1].split('/')
        host_port = url_parts[0]
        host = host_port.split(':')[0]
        port = int(host_port.split(':')[1]) if ':' in host_port else 5432
        
        logger.info(f"Testing network connectivity to {host}:{port}")
        
        # Test TCP connection
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            return jsonify({
                'status': 'success',
                'message': f'Network connection to {host}:{port} successful',
                'host': host,
                'port': port
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'Network connection to {host}:{port} failed',
                'host': host,
                'port': port,
                'error_code': result,
                'solution': 'Check security group rules'
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': 'Network test failed',
            'error': str(e)
        }), 500

@app.route('/db-test')
def test_database():
    try:
        logger.info("Testing database connection...")
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Database connection timed out after 15 seconds")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(15)  # 15 second timeout
        
        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            
        signal.alarm(0)  # Cancel timeout
        logger.info("Database connection successful")
        return jsonify({
            'status': 'success',
            'message': 'Database connection working',
            'database_version': version
        })
    except TimeoutError as e:
        signal.alarm(0)
        logger.error(f"Database connection timeout: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Database connection timed out',
            'error': 'Network connectivity issue - check VPC connector and security groups'
        }), 500
    except Exception as e:
        signal.alarm(0)
        logger.error(f"Database connection failed: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Database connection failed',
            'error': str(e),
            'error_type': type(e).__name__
        }), 500

@app.route('/ping')
def ping():
    return 'pong', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)