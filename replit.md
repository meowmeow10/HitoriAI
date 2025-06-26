# Hitori AI Chat Assistant

## Overview

Hitori is a Flask-based AI chat assistant featuring a custom self-trained AI model. The application provides a web interface for conversing with Hitori's learning AI, complete with voice input/output capabilities, session management, and a modern dark-themed UI built with Bootstrap. The AI learns and improves from each conversation.

## System Architecture

### Frontend Architecture
- **Framework**: Vanilla JavaScript with Bootstrap 5 (dark theme)
- **UI Components**: Chat bubbles, voice controls, loading states
- **Speech Integration**: Web Speech API for voice input and synthesis
- **Responsive Design**: Mobile-first approach with Bootstrap grid system

### Backend Architecture
- **Framework**: Flask (Python web framework)
- **AI Model**: Custom self-trained AI using pattern matching and machine learning
- **Session Management**: Flask sessions with UUID-based session IDs
- **CORS Support**: Flask-CORS for cross-origin requests
- **WSGI Server**: Gunicorn for production deployment
- **AI Learning**: Knowledge base with JSON storage for persistent learning

### Data Storage
- **Session Storage**: Flask sessions (server-side, likely file-based by default)
- **Message History**: Stored in session during active conversation
- **Database**: Custom Neon PostgreSQL database for persistent knowledge storage
- **Knowledge Base**: AI learning data stored in PostgreSQL with automatic web scraping
- **Conversation History**: User interactions tracked for continuous AI improvement

## Key Components

### Core Application Files
- `main.py`: Application entry point (imports Flask app)
- `app.py`: Main Flask application with routes and custom AI integration
- `ai_model.py`: Self-trained AI model with learning capabilities
- `templates/index.html`: Single-page chat interface
- `static/js/app.js`: Frontend JavaScript handling chat logic and speech features
- `static/css/style.css`: Custom styling for chat interface

### Route Structure
- `GET /`: Serves the main chat interface
- `POST /chat`: Handles message processing and AI responses
- `POST /clear`: Clears chat history for current session
- `GET /health`: Health check with AI model status
- `GET /stats`: Returns AI learning statistics

### Frontend Features
- Real-time chat interface with user/assistant message bubbles
- Voice input using Web Speech Recognition
- Text-to-speech for AI responses
- AI learning statistics display
- Clear chat functionality
- Loading states and error handling
- Responsive design with dark theme

## Data Flow

1. **User Input**: User types message or uses voice input
2. **Session Management**: Flask creates/maintains session with unique ID
3. **Message Processing**: Frontend sends POST request to `/chat` endpoint
4. **AI Processing**: Custom AI model analyzes message and generates contextual response
5. **Learning**: AI updates knowledge base with new keywords and patterns
6. **Response Handling**: AI response returned to frontend and displayed
7. **Voice Output**: Optional text-to-speech conversion of AI responses

## External Dependencies

### Python Packages
- `flask`: Web framework
- `flask-cors`: Cross-origin resource sharing
- `flask-sqlalchemy`: Database ORM (prepared for future use)
- `openai`: OpenAI API client
- `gunicorn`: WSGI HTTP server
- `psycopg2-binary`: PostgreSQL adapter (prepared for future use)
- `email-validator`: Email validation utilities

### Frontend Dependencies
- Bootstrap 5 (dark theme from Replit CDN)
- Font Awesome icons
- Web Speech API (browser native)

### Environment Variables
- `SESSION_SECRET`: Flask session encryption key (auto-generated in development)

## Deployment Strategy

### Development Environment
- **Platform**: Replit with Nix package management
- **Python Version**: 3.11
- **Local Server**: Gunicorn with hot reload
- **Port**: 5000 with automatic port detection

### Production Deployment
- **Target**: Autoscale deployment on Replit
- **Server**: Gunicorn with multiple workers
- **Binding**: 0.0.0.0:5000 for external access
- **Process Management**: Replit workflows for automated startup

### Infrastructure
- **Nix Packages**: OpenSSL and PostgreSQL available
- **Build System**: UV lock file for dependency management
- **Environment**: Stable Nix channel (24.05)

## Changelog

```
Changelog:
- June 26, 2025: Initial setup with OpenAI integration
- June 26, 2025: Replaced OpenAI with custom self-trained AI model
- June 26, 2025: Added AI learning statistics and knowledge persistence
- June 26, 2025: Completed functional testing - user confirmed working
- June 26, 2025: Added PostgreSQL database and web scraping capabilities for rapid learning
- June 26, 2025: Enhanced knowledge extraction for specific topics like anime/entertainment
- June 26, 2025: Implemented fallback training system that works with or without database
- June 26, 2025: Successfully tested with K-On! topic - AI now learns and responds with factual information
- June 26, 2025: Connected to custom Neon database for cloud-based knowledge persistence
- June 26, 2025: Fixed AI responses to be natural and conversational, removing technical formatting issues
```

## User Preferences

```
Preferred communication style: Simple, everyday language.
```

### Architecture Notes

The application is structured as a simple but extensible chat interface. Key architectural decisions include:

- **Single-page application**: Reduces complexity and provides smooth user experience
- **Session-based storage**: Temporary conversation history without permanent persistence
- **OpenAI integration**: Direct API calls for reliable AI responses
- **Voice capabilities**: Enhanced accessibility through speech recognition and synthesis
- **Modular frontend**: Separate JavaScript class for chat functionality
- **Bootstrap theming**: Consistent dark theme matching Replit's interface
- **Database preparation**: SQLAlchemy and PostgreSQL ready for future data persistence features

The architecture supports future enhancements like user authentication, conversation persistence, and advanced AI features while maintaining simplicity in the current implementation.