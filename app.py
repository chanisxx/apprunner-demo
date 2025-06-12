from flask import Flask, render_template, jsonify
import os

app = Flask(__name__)

@app.route('/')
def home():
    return '''
    <h1>Flask App on AWS App Runner</h1>
    <p>Your Flask application is running successfully!</p>
    <p>Flask Version: 3.1.1</p>
    <a href="/health">Check Health</a> | 
    <a href="/api/data">API Data</a>
    '''

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy',
        'message': 'Flask app is running on AWS App Runner',
        'flask_version': '3.1.1'
    })

@app.route('/api/data')
def get_data():
    return jsonify({
        'data': ['item1', 'item2', 'item3'],
        'timestamp': '2025-06-12',
        'environment': os.getenv('FLASK_ENV', 'development')
    })

# Health check endpoint for App Runner
@app.route('/ping')
def ping():
    return 'pong', 200

if __name__ == '__main__':
    # For local development
    app.run(host='0.0.0.0', port=8000, debug=True)