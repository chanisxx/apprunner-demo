from flask import Flask, jsonify
import logging
import os
import json
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import urllib.request
import urllib.parse

# Force new deployment - updated requirements.txt with compatible urllib3/requests
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
    return '''
    <h1>Flask App on AWS App Runner</h1>
    <p>Your Flask application is running successfully!</p>
    <p>Connected to custom VPC and RDS PostgreSQL</p>
    <a href="/internet-test">Internet Test</a> | 
    <a href="/network-test">Network Test</a> |
    <a href="/db-test">Database Test</a> |
    <a href="/openai-test">OpenAI Test</a>
    '''

@app.route('/internet-test')
def internet_test():
    import socket
    
    try:
        # Simple TCP connection test to OpenAI API
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex(('api.openai.com', 443))
        sock.close()
        
        if result == 0:
            return jsonify({
                'status': 'success',
                'message': 'Internet connectivity to OpenAI API successful'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Cannot reach OpenAI API',
                'error_code': result
            }), 500
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': 'Internet test failed',
            'error': str(e)
        }), 500

@app.route('/network-test')
def network_test():
    """Test network connectivity to database"""
    import socket
    
    try:
        # Extract host and port from DATABASE_URL
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
                'error_code': result
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
        
        # Extract database host from DATABASE_URL for verification
        db_host = "unknown"
        try:
            if '@' in DATABASE_URL:
                host_part = DATABASE_URL.split('@')[1].split('/')[0]
                db_host = host_part.split(':')[0]
        except:
            pass
        
        with db_engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            
        logger.info("Database connection successful")
        return jsonify({
            'status': 'success',
            'message': 'Database connection working',
            'database_version': version,
            'database_host': db_host
        })
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Database connection failed',
            'error': str(e)
        }), 500

@app.route('/openai-test')
def openai_test():
    openai_api_key = os.getenv('OPENAI_API_KEY')
    if not openai_api_key:
        return jsonify({
            'status': 'error',
            'message': 'OPENAI_API_KEY environment variable not set'
        }), 500
    
    try:
        # Create request data
        data = {
            'model': 'gpt-3.5-turbo',
            'messages': [
                {'role': 'user', 'content': 'Hello! who are you?'}
            ],
            'max_tokens': 50
        }
        
        # Encode data
        data_bytes = json.dumps(data).encode('utf-8')
        
        # Create request
        req = urllib.request.Request(
            'https://api.openai.com/v1/chat/completions',
            data=data_bytes,
            headers={
                'Authorization': f'Bearer {openai_api_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'AppRunner-Test/1.0'
            }
        )
        
        # Make request
        response = urllib.request.urlopen(req, timeout=30)
        
        if response.status == 200:
            result = json.loads(response.read().decode('utf-8'))
            message = result['choices'][0]['message']['content']
            return jsonify({
                'status': 'success',
                'message': 'OpenAI API call successful',
                'response': message,
                'tokens_used': result['usage']['total_tokens']
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'OpenAI API error: {response.status}',
                'response_text': response.read().decode('utf-8')
            }), 500
            
    except urllib.error.HTTPError as e:
        # 401 is expected without API key, but means connectivity works
        if e.code == 401:
            return jsonify({
                'status': 'success',
                'message': 'OpenAI API reachable (401 expected without API key)',
                'response': 'Authentication required'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'OpenAI API error: {e.code}',
                'response_text': e.read().decode('utf-8')
            }), 500
    except urllib.error.URLError as e:
        return jsonify({
            'status': 'error',
            'message': 'Connection error to OpenAI API',
            'error': str(e)
        }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': 'OpenAI API call failed',
            'error': str(e)
        }), 500

@app.route('/ping')
def ping():
    return 'pong', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)