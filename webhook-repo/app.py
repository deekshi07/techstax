from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime
import os
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
# MongoDB connection
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client['github_events']
collection = db['events']

# Helper to parse GitHub webhook payloads
def parse_github_event(payload, event_type):
    data = {
        'request_id': '',
        'author': '',
        'action': event_type.upper(),
        'from_branch': '',
        'to_branch': '',
        'timestamp': ''
    }
    if event_type == 'push':
        data['request_id'] = payload['after']
        data['author'] = payload['pusher']['name']
        data['from_branch'] = payload['ref'].split('/')[-1]
        data['to_branch'] = payload['ref'].split('/')[-1]
        data['timestamp'] = datetime.utcnow().isoformat()
    elif event_type == 'pull_request':
        pr = payload['pull_request']
        data['request_id'] = str(pr['id'])
        data['author'] = pr['user']['login']
        data['from_branch'] = pr['head']['ref']
        data['to_branch'] = pr['base']['ref']
        data['timestamp'] = pr['created_at']
    elif event_type == 'merge':
        pr = payload['pull_request']
        data['request_id'] = str(pr['id'])
        data['author'] = pr['user']['login']
        data['from_branch'] = pr['head']['ref']
        data['to_branch'] = pr['base']['ref']
        data['timestamp'] = datetime.utcnow().isoformat()
    return data

@app.route('/webhook', methods=['POST'])
def github_webhook():
    event_type = request.headers.get('X-GitHub-Event')
    payload = request.json
    if event_type in ['push', 'pull_request']:
        data = parse_github_event(payload, event_type)
        collection.insert_one(data)
        return jsonify({'status': 'success'}), 201
    elif event_type == 'merge':
        data = parse_github_event(payload, event_type)
        collection.insert_one(data)
        return jsonify({'status': 'success'}), 201
    return jsonify({'status': 'ignored'}), 200

@app.route('/events', methods=['GET'])
def get_events():
   
    events = list(collection.find().sort('timestamp', -1).limit(10))
    for event in events:
        event['_id'] = str(event['_id'])
    return jsonify(events)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
