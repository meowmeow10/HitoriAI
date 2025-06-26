import os
import logging
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from ai_model import HitoriAI
import uuid

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")

# Enable CORS
CORS(app)

# Initialize Hitori AI
hitori_ai = HitoriAI()

@app.route('/')
def index():
    """Serve the main chat interface"""
    # Initialize session if needed
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session['messages'] = []
    
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages and return AI responses"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Get session ID for user tracking
        session_id = session.get('session_id', 'anonymous')
        
        # Get response from Hitori AI
        ai_response = hitori_ai.process_message(user_message, user_id=session_id)
        
        return jsonify({
            'response': ai_response,
            'success': True
        })
        
    except Exception as e:
        logging.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            'error': f'An error occurred while processing your message: {str(e)}',
            'success': False
        }), 500

@app.route('/clear', methods=['POST'])
def clear_chat():
    """Clear the chat history"""
    try:
        # Clear session messages
        session['messages'] = []
        session.modified = True
        
        # Clear AI conversation memory for this session
        session_id = session.get('session_id', 'anonymous')
        hitori_ai.conversation_memory = [
            msg for msg in hitori_ai.conversation_memory 
            if msg.get('user_id') != session_id
        ]
        
        return jsonify({'success': True, 'message': 'Chat history cleared'})
    except Exception as e:
        logging.error(f"Error clearing chat: {str(e)}")
        return jsonify({'error': 'Failed to clear chat history', 'success': False}), 500

@app.route('/health')
def health():
    """Health check endpoint"""
    stats = hitori_ai.get_conversation_stats()
    return jsonify({
        'status': 'healthy',
        'ai_model': 'Hitori Self-Trained AI',
        'total_interactions': stats['total_interactions'],
        'topics_learned': stats['topics_learned'],
        'patterns_learned': stats['patterns_learned']
    })

@app.route('/stats')
def stats():
    """Get AI learning statistics"""
    return jsonify(hitori_ai.get_conversation_stats())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
