# Hitori AI Chat Assistant

## Overview

Hitori is a Flask-based AI chat assistant that provides a web interface for conversing with OpenAI's GPT models. The application features a responsive chat interface with voice input/output capabilities, session management, and a modern dark-themed UI built with Bootstrap.

## System Architecture

### Frontend Architecture
- **Framework**: Vanilla JavaScript with Bootstrap 5 (dark theme)
- **UI Components**: Chat bubbles, voice controls, loading states
- **Speech Integration**: Web Speech API for voice input and synthesis
- **Responsive Design**: Mobile-first approach with Bootstrap grid system

### Backend Architecture
- **Framework**: Flask (Python web framework)
- **API Integration**: OpenAI API for AI responses
- **Session Management**: Flask sessions with UUID-based session IDs
- **CORS Support**: Flask-CORS for cross-origin requests
- **WSGI Server**: Gunicorn for production deployment

### Data Storage
- **Session Storage**: Flask sessions (server-side, likely file-based by default)
- **Message History**: Stored in session during active conversation
- **Database**: PostgreSQL packages available but not yet implemented

## Key Components

### Core Application Files
- `main.py`: Application entry point (imports Flask app)
- `app.py`: Main Flask application with routes and OpenAI integration
- `templates/index.html`: Single-page chat interface
- `static/js/app.js`: Frontend JavaScript handling chat logic and speech features
- `static/css/style.css`: Custom styling for chat interface

### Route Structure
- `GET /`: Serves the main chat interface
- `POST /chat`: Handles message processing and AI responses

### Frontend Features
- Real-time chat interface with user/assistant message bubbles
- Voice input using Web Speech Recognition
- Text-to-speech for AI responses
- Clear chat functionality
- Loading states and error handling
- Responsive design with dark theme

## Data Flow

1. **User Input**: User types message or uses voice input
2. **Session Management**: Flask creates/maintains session with unique ID
3. **Message Processing**: Frontend sends POST request to `/chat` endpoint
4. **AI Integration**: Backend calls OpenAI API with conversation context
5. **Response Handling**: AI response returned to frontend and displayed
6. **Voice Output**: Optional text-to-speech conversion of AI responses

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
- `OPENAI_API_KEY`: Required for AI functionality
- `SESSION_SECRET`: Flask session encryption key

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
- June 26, 2025. Initial setup
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