from flask import Flask, request, jsonify
from datetime import datetime
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')

client = None
collection = None
_memory_events = []

try:
    from pymongo import MongoClient
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
    client.server_info() # Test connectivity
    db = client['github_events']
    collection = db['events']
except Exception:
    collection = None

def parse_github_event(payload, event_type):
    data = {
        'request_id': '',
        'author': '',
        'action': event_type.upper(),
        'from_branch': '',
        'to_branch': '',
        'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    }
    if event_type == 'push':
        data['request_id'] = payload.get('after', 'commit_' + str(datetime.utcnow().timestamp())[:8])
        data['author'] = payload.get('pusher', {}).get('name', 'deekshi07')
        ref = payload.get('ref', 'refs/heads/main')
        data['from_branch'] = ref.split('/')[-1]
        data['to_branch'] = ref.split('/')[-1]
    elif event_type in ['pull_request', 'merge']:
        pr = payload.get('pull_request', {})
        data['request_id'] = str(pr.get('id', 'pr_' + str(datetime.utcnow().timestamp())[:8]))
        data['author'] = pr.get('user', {}).get('login', 'deekshi07')
        data['from_branch'] = pr.get('head', {}).get('ref', 'feature/update')
        data['to_branch'] = pr.get('base', {}).get('ref', 'main')
        data['timestamp'] = pr.get('created_at', data['timestamp'])
    return data

@app.route('/')
def home():
    return jsonify({
        'service': 'GitHub Webhook Ingestion API',
        'status': 'online',
        'storage': 'MongoDB' if collection is not None else 'In-Memory Fallback',
        'endpoints': ['/webhook', '/events', '/simulate']
    })

@app.route('/webhook', methods=['POST'])
def github_webhook():
    event_type = request.headers.get('X-GitHub-Event', 'push').lower()
    payload = request.json or {}
    
    # Check if pull_request was merged
    if event_type == 'pull_request' and payload.get('action') == 'closed' and payload.get('pull_request', {}).get('merged'):
        event_type = 'merge'

    if event_type in ['push', 'pull_request', 'merge']:
        data = parse_github_event(payload, event_type)
        if collection is not None:
            collection.insert_one(data)
        else:
            data['_id'] = f"ev_{len(_memory_events) + 1}"
            _memory_events.append(data)
        return jsonify({'status': 'success', 'data': data}), 201
    return jsonify({'status': 'ignored', 'reason': f'Event type {event_type} not tracked'}), 200

@app.route('/events', methods=['GET'])
def get_events():
    if collection is not None:
        events = list(collection.find().sort('timestamp', -1).limit(20))
        for event in events:
            event['_id'] = str(event['_id'])
        return jsonify(events)
    return jsonify(list(reversed(_memory_events)))

@app.route('/simulate', methods=['POST'])
def simulate_event():
    """Generates mock GitHub webhook payload for testing without webhook tunnels."""
    payload = request.json or {}
    event_type = payload.get('type', 'push')
    
    mock_payload = {}
    if event_type == 'push':
        mock_payload = {
            'after': '7a8b9c1d2e3f',
            'pusher': {'name': payload.get('author', 'deekshi07')},
            'ref': f"refs/heads/{payload.get('branch', 'main')}"
        }
    elif event_type == 'pull_request':
        mock_payload = {
            'pull_request': {
                'id': 104,
                'user': {'login': payload.get('author', 'deekshi07')},
                'head': {'ref': payload.get('from_branch', 'feature/auth-pipeline')},
                'base': {'ref': payload.get('to_branch', 'main')},
                'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            }
        }
    elif event_type == 'merge':
        mock_payload = {
            'action': 'closed',
            'pull_request': {
                'id': 104,
                'merged': True,
                'user': {'login': payload.get('author', 'deekshi07')},
                'head': {'ref': payload.get('from_branch', 'feature/auth-pipeline')},
                'base': {'ref': payload.get('to_branch', 'main')},
                'created_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            }
        }

    data = parse_github_event(mock_payload, event_type)
    if collection is not None:
        collection.insert_one(data)
    else:
        data['_id'] = f"ev_{len(_memory_events) + 1}"
        _memory_events.append(data)

    return jsonify({'status': 'simulated', 'event': data}), 201

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, port=port)
