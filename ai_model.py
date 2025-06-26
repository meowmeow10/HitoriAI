import json
import os
import random
import re
from datetime import datetime
from collections import defaultdict, Counter
import logging
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker
from models import Base, Knowledge, ConversationHistory, LearningPattern, WebSource, TopicKeyword
from web_scraper import WebKnowledgeScraper

class HitoriAI:
    """
    Hitori AI - A self-learning conversational AI assistant
    Uses pattern matching, keyword analysis, database storage, and web scraping
    """
    
    def __init__(self, knowledge_file='hitori_knowledge.json', database_url=None):
        # Initialize database connection - prioritize Neon database
        self.database_url = (database_url or 
                           os.environ.get('NEON_DATABASE_URL') or 
                           os.environ.get('DATABASE_URL'))
        self.engine = None
        self.Session = None
        self.db_session = None
        self.web_scraper = None
        
        if self.database_url:
            try:
                # Configure for Neon database
                connect_args = {"sslmode": "require"} if "neon.tech" in self.database_url else {"sslmode": "prefer"}
                
                self.engine = create_engine(
                    self.database_url,
                    pool_recycle=300,
                    pool_pre_ping=True,
                    connect_args=connect_args
                )
                Base.metadata.create_all(self.engine)
                self.Session = sessionmaker(bind=self.engine)
                self.db_session = self.Session()
                self.web_scraper = WebKnowledgeScraper(self.db_session)
                
                # Log which database we're using
                if "neon.tech" in self.database_url:
                    logging.info("Connected to Neon database successfully")
                else:
                    logging.info("Connected to PostgreSQL database")
                    
            except Exception as e:
                logging.error(f"Database connection failed: {e}")
                self.db_session = None
                self.web_scraper = None
        
        # Fallback to file-based storage
        self.knowledge_file = knowledge_file
        self.knowledge_base = self.load_knowledge()
        self.conversation_memory = []
        self.user_preferences = {}
        self.response_patterns = self.initialize_response_patterns()
        self.context_keywords = []
        
    def load_knowledge(self):
        """Load existing knowledge base or create new one"""
        if os.path.exists(self.knowledge_file):
            try:
                with open(self.knowledge_file, 'r') as f:
                    return json.load(f)
            except:
                logging.warning("Could not load knowledge file, creating new one")
        
        return self.create_initial_knowledge_base()
    
    def save_knowledge(self):
        """Save current knowledge base to file"""
        try:
            with open(self.knowledge_file, 'w') as f:
                json.dump(self.knowledge_base, f, indent=2)
        except Exception as e:
            logging.error(f"Could not save knowledge base: {e}")
    
    def create_initial_knowledge_base(self):
        """Create initial knowledge base with basic responses and patterns"""
        return {
            "responses": {
                "greeting": [
                    "Hello! I'm Hitori, your AI assistant. How can I help you today?",
                    "Hi there! I'm Hitori. What would you like to chat about?",
                    "Hey! I'm Hitori, nice to meet you. What's on your mind?",
                    "Hello! I'm Hitori, ready to assist you. What can I do for you?"
                ],
                "goodbye": [
                    "Goodbye! It was great chatting with you.",
                    "See you later! Feel free to come back anytime.",
                    "Take care! I'll be here when you need me.",
                    "Bye! Thanks for the conversation."
                ],
                "thanks": [
                    "You're welcome! Happy to help.",
                    "No problem at all! Glad I could assist.",
                    "My pleasure! Let me know if you need anything else.",
                    "You're very welcome! I'm here to help."
                ],
                "how_are_you": [
                    "I'm doing great, thank you for asking! How are you?",
                    "I'm wonderful! Always excited to chat. How about you?",
                    "I'm doing well! Ready to help with whatever you need.",
                    "I'm fantastic! Thanks for asking. What's new with you?"
                ],
                "what_are_you": [
                    "I'm Hitori, your AI assistant! I'm here to chat, help, and learn from our conversations.",
                    "I'm Hitori, an AI created to be your helpful companion. I can discuss topics, answer questions, and assist with various tasks.",
                    "I'm Hitori! I'm an AI assistant designed to be conversational, helpful, and friendly.",
                    "I'm Hitori, your personal AI assistant. I love chatting and helping people with whatever they need."
                ],
                "help": [
                    "I can help with many things! Ask me questions, have a conversation, get advice, or just chat about your interests.",
                    "I'm here to assist! I can answer questions, discuss topics, provide information, or simply have a friendly chat.",
                    "I can help with various tasks - answering questions, having conversations, providing suggestions, or just being a good listener.",
                    "I'm ready to help! Whether you need information, want to chat, or need assistance with something, I'm here for you."
                ],
                "default": [
                    "That's interesting! Tell me more about that.",
                    "I find that fascinating. What else would you like to discuss?",
                    "That's a great point. Can you elaborate?",
                    "I'd love to hear more about your thoughts on this.",
                    "That's quite intriguing. What's your take on it?",
                    "I appreciate you sharing that with me. What else is on your mind?"
                ]
            },
            "patterns": {
                "greeting": ["hello", "hi", "hey", "good morning", "good afternoon", "good evening"],
                "goodbye": ["bye", "goodbye", "see you", "farewell", "talk to you later", "gtg"],
                "thanks": ["thank", "thanks", "appreciate", "grateful"],
                "how_are_you": ["how are you", "how do you feel", "how's it going"],
                "what_are_you": ["what are you", "who are you", "tell me about yourself"],
                "help": ["help", "assist", "support", "what can you do"]
            },
            "learned_responses": {},
            "topic_knowledge": {},
            "user_interactions": 0,
            "last_updated": datetime.now().isoformat()
        }
    
    def initialize_response_patterns(self):
        """Initialize response generation patterns"""
        return {
            "question_starters": [
                "That's a great question about",
                "When it comes to",
                "I think about",
                "From what I understand about",
                "Regarding"
            ],
            "opinion_phrases": [
                "In my view,",
                "I believe that",
                "From my perspective,",
                "I think that",
                "It seems to me that"
            ],
            "continuation_phrases": [
                "What do you think about that?",
                "How does that sound to you?",
                "What's your experience with this?",
                "I'd love to hear your thoughts.",
                "What would you add to that?"
            ]
        }
    
    def process_message(self, message, user_id=None):
        """Process user message and generate appropriate response"""
        message = message.strip().lower()
        
        # Store conversation in memory
        self.conversation_memory.append({
            "user": message,
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id
        })
        
        # Update interaction count
        self.knowledge_base["user_interactions"] += 1
        
        # Extract keywords and context
        keywords = self.extract_keywords(message)
        self.context_keywords.extend(keywords)
        self.context_keywords = self.context_keywords[-20:]  # Keep last 20 keywords for context
        
        # Find appropriate response (use enhanced version if database available)
        if self.db_session and keywords:
            response = self.generate_enhanced_response(message, keywords)
        else:
            response = self.generate_response(message, keywords)
        
        # Learn from interaction
        self.learn_from_interaction(message, response, keywords)
        
        # Store in database if available
        if self.db_session:
            self.store_conversation_in_database(message, response, keywords, user_id)
        
        # Store AI response in memory
        self.conversation_memory.append({
            "ai": response,
            "timestamp": datetime.now().isoformat()
        })
        
        # Save knowledge periodically
        if self.knowledge_base["user_interactions"] % 10 == 0:
            self.save_knowledge()
        
        return response
    
    def extract_keywords(self, message):
        """Extract meaningful keywords from message"""
        # Remove common stop words
        stop_words = {
            'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 'your', 'yours',
            'yourself', 'yourselves', 'he', 'him', 'his', 'himself', 'she', 'her', 'hers',
            'herself', 'it', 'its', 'itself', 'they', 'them', 'their', 'theirs', 'themselves',
            'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is', 'are',
            'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having', 'do', 'does',
            'did', 'doing', 'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until',
            'while', 'of', 'at', 'by', 'for', 'with', 'through', 'during', 'before', 'after',
            'above', 'below', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again',
            'further', 'then', 'once', 'know', 'tell', 'about'
        }
        
        # First look for special patterns including anime/manga titles
        special_patterns = [
            r'\bK-On!?\b',  # K-On with or without exclamation
            r'\bBocchi[^a-z]*Rock\b',  # Bocchi the Rock variations
            r'\b[A-Za-z]+[!-][A-Za-z]*\b',  # General hyphenated/exclamation words
            r'\b[A-Z][a-z]*-[A-Z][a-z]*\b'  # Capitalized hyphenated words
        ]
        
        special_keywords = []
        for pattern in special_patterns:
            matches = re.findall(pattern, message, re.IGNORECASE)
            special_keywords.extend(matches)
        
        # Extract words and filter out stop words
        words = re.findall(r'\b[a-zA-Z]+\b', message.lower())
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Add special keywords back (preserve original case but also add lowercase)
        for kw in special_keywords:
            keywords.append(kw.lower())
            if kw.lower() != kw:
                keywords.append(kw)
        
        return list(set(keywords))  # Remove duplicates
    
    def find_pattern_match(self, message):
        """Find if message matches any known patterns"""
        for pattern_type, patterns in self.knowledge_base["patterns"].items():
            for pattern in patterns:
                if pattern in message:
                    return pattern_type
        return None
    
    def generate_response(self, message, keywords):
        """Generate appropriate response based on message analysis"""
        # Check for direct pattern matches first
        pattern_match = self.find_pattern_match(message)
        if pattern_match and pattern_match in self.knowledge_base["responses"]:
            return random.choice(self.knowledge_base["responses"][pattern_match])
        
        # Check learned responses
        for learned_pattern, responses in self.knowledge_base["learned_responses"].items():
            if learned_pattern in message:
                return random.choice(responses)
        
        # Check topic knowledge
        for keyword in keywords:
            if keyword in self.knowledge_base["topic_knowledge"]:
                topic_info = self.knowledge_base["topic_knowledge"][keyword]
                return self.generate_contextual_response(keyword, topic_info, keywords)
        
        # Generate response based on keywords and context
        if keywords:
            return self.generate_keyword_response(keywords)
        
        # Default response
        return random.choice(self.knowledge_base["responses"]["default"])
    
    def generate_contextual_response(self, main_keyword, topic_info, all_keywords):
        """Generate response using topic knowledge"""
        response_parts = []
        
        # Add opinion or question starter
        if random.choice([True, False]) and self.response_patterns.get("question_starters"):
            starter = random.choice(self.response_patterns["question_starters"])
            response_parts.append(f"{starter} {main_keyword},")
        
        # Add topic information
        if "facts" in topic_info and topic_info["facts"]:
            fact = random.choice(topic_info["facts"])
            response_parts.append(fact)
        
        # Add continuation question
        if random.choice([True, False]) and self.response_patterns.get("continuation_phrases"):
            continuation = random.choice(self.response_patterns["continuation_phrases"])
            response_parts.append(continuation)
        
        if response_parts:
            return " ".join(response_parts)
        else:
            # Fallback response if no parts were generated
            return f"That's interesting about {main_keyword}. What would you like to know more about?"
    
    def generate_keyword_response(self, keywords):
        """Generate response based on keywords"""
        main_keyword = keywords[0] if keywords else "that"
        
        responses = [
            f"I find {main_keyword} quite interesting. What specifically interests you about it?",
            f"That's a great topic about {main_keyword}. Can you tell me more?",
            f"I'd love to learn more about {main_keyword} from your perspective.",
            f"When you mention {main_keyword}, what comes to mind first?",
            f"I'm curious about your experience with {main_keyword}.",
            f"That's fascinating! How did you get interested in {main_keyword}?"
        ]
        
        return random.choice(responses)
    
    def learn_from_interaction(self, user_message, ai_response, keywords):
        """Learn from user interaction to improve future responses"""
        # Store keyword associations
        for keyword in keywords:
            if keyword not in self.knowledge_base["topic_knowledge"]:
                self.knowledge_base["topic_knowledge"][keyword] = {
                    "mentions": 1,
                    "contexts": [user_message],
                    "facts": []
                }
            else:
                self.knowledge_base["topic_knowledge"][keyword]["mentions"] += 1
                self.knowledge_base["topic_knowledge"][keyword]["contexts"].append(user_message)
                # Keep only recent contexts
                if len(self.knowledge_base["topic_knowledge"][keyword]["contexts"]) > 5:
                    self.knowledge_base["topic_knowledge"][keyword]["contexts"] = \
                        self.knowledge_base["topic_knowledge"][keyword]["contexts"][-5:]
        
        # Learn new patterns from user message
        if len(user_message) > 10:  # Only learn from substantial messages
            self.add_learned_pattern(user_message, ai_response)
    
    def learn_conversation_patterns(self, user_message, ai_response, keywords):
        """Learn conversation patterns for better responses"""
        if "conversation_patterns" not in self.knowledge_base:
            self.knowledge_base["conversation_patterns"] = {}
        
        # Learn question patterns
        if '?' in user_message:
            pattern_type = "questions"
            if pattern_type not in self.knowledge_base["conversation_patterns"]:
                self.knowledge_base["conversation_patterns"][pattern_type] = {}
            
            for keyword in keywords:
                if keyword not in self.knowledge_base["conversation_patterns"][pattern_type]:
                    self.knowledge_base["conversation_patterns"][pattern_type][keyword] = []
                self.knowledge_base["conversation_patterns"][pattern_type][keyword].append({
                    "question": user_message,
                    "response": ai_response,
                    "timestamp": datetime.now().isoformat()
                })
        
        # Learn enthusiasm patterns
        if any(word in user_message.lower() for word in ['awesome', 'amazing', 'love', 'great', '!']):
            pattern_type = "enthusiasm"
            if pattern_type not in self.knowledge_base["conversation_patterns"]:
                self.knowledge_base["conversation_patterns"][pattern_type] = {}
            
            for keyword in keywords:
                if keyword not in self.knowledge_base["conversation_patterns"][pattern_type]:
                    self.knowledge_base["conversation_patterns"][pattern_type][keyword] = []
                self.knowledge_base["conversation_patterns"][pattern_type][keyword].append({
                    "message": user_message,
                    "response": ai_response,
                    "timestamp": datetime.now().isoformat()
                })
    
    def add_learned_pattern(self, user_message, ai_response):
        """Enhanced pattern learning with context awareness"""
        # Extract intent from message
        intent = self.extract_message_intent(user_message)
        
        # Create pattern key based on intent and message structure
        pattern_key = f"{intent}:{user_message[:30]}"
        
        if pattern_key not in self.knowledge_base["learned_responses"]:
            self.knowledge_base["learned_responses"][pattern_key] = {
                "responses": [],
                "success_count": 0,
                "total_uses": 0,
                "intent": intent
            }
        
        # Don't duplicate responses
        pattern_data = self.knowledge_base["learned_responses"][pattern_key]
        if ai_response not in pattern_data["responses"]:
            pattern_data["responses"].append(ai_response)
            pattern_data["total_uses"] += 1
    
    def extract_message_intent(self, message):
        """Extract the intent from a user message"""
        message_lower = message.lower()
        
        if '?' in message or any(word in message_lower for word in ['what', 'how', 'why', 'when', 'where', 'who']):
            return "question"
        elif any(word in message_lower for word in ['hello', 'hi', 'hey', 'good morning']):
            return "greeting"
        elif any(word in message_lower for word in ['bye', 'goodbye', 'see you']):
            return "farewell"
        elif any(word in message_lower for word in ['thank', 'thanks', 'appreciate']):
            return "gratitude"
        elif any(word in message_lower for word in ['help', 'assist', 'support']):
            return "help_request"
        elif any(word in message_lower for word in ['tell me', 'explain', 'describe']):
            return "information_request"
        elif '!' in message or any(word in message_lower for word in ['awesome', 'amazing', 'love', 'excited']):
            return "enthusiasm"
        else:
            return "general"
    
    def get_conversation_stats(self):
        """Get statistics about conversations"""
        stats = {
            "total_interactions": self.knowledge_base["user_interactions"],
            "topics_learned": len(self.knowledge_base["topic_knowledge"]),
            "patterns_learned": len(self.knowledge_base["learned_responses"]),
            "last_updated": self.knowledge_base["last_updated"]
        }
        
        # Add database stats if available
        if self.db_session:
            try:
                db_knowledge_count = self.db_session.query(Knowledge).count()
                db_conversations = self.db_session.query(ConversationHistory).count()
                db_patterns = self.db_session.query(LearningPattern).count()
                
                stats.update({
                    "database_knowledge": db_knowledge_count,
                    "database_conversations": db_conversations,
                    "database_patterns": db_patterns,
                    "web_scraping_enabled": self.web_scraper is not None
                })
            except Exception as e:
                logging.error(f"Error getting database stats: {e}")
        
        return stats
    
    def train_from_web(self, topics=None, max_sources=5):
        """Train AI by scraping web sources for knowledge"""
        try:
            # Create a simple web scraper even without database
            if not self.web_scraper:
                from web_scraper import WebKnowledgeScraper
                simple_scraper = WebKnowledgeScraper(None)
            else:
                simple_scraper = self.web_scraper
            
            # Get URLs based on topics
            if topics:
                # Create specific Wikipedia URLs for the topics
                urls = []
                for topic in topics:
                    clean_topic = topic.replace(' ', '_').replace('!', '%21')
                    urls.append(f'https://en.wikipedia.org/wiki/{clean_topic}')
                urls.extend(simple_scraper.get_topic_suggestions(topics)[:2])
            else:
                urls = simple_scraper.default_sources
            
            # Scrape web sources
            results = simple_scraper.scrape_multiple_sources(urls, max_sources)
            
            # Store knowledge - try database first, fallback to memory
            knowledge_added = 0
            if self.db_session:
                try:
                    for topic, knowledge_items in results['knowledge_by_topic'].items():
                        for item in knowledge_items:
                            # Store in database
                            knowledge = Knowledge(
                                topic=item['topic'],
                                content=item['content'],
                                source=item['source'],
                                confidence_score=item['confidence_score'],
                                is_verified=False
                            )
                            self.db_session.add(knowledge)
                            knowledge_added += 1
                    
                    self.db_session.commit()
                except Exception as db_error:
                    logging.warning(f"Database storage failed, using memory: {db_error}")
                    self.db_session.rollback()
                    # Fall back to memory storage
                    knowledge_added = self.store_knowledge_in_memory(results['knowledge_by_topic'])
            else:
                # Store in memory/file system
                knowledge_added = self.store_knowledge_in_memory(results['knowledge_by_topic'])
            
            return {
                "success": True,
                "sources_scraped": results['successful_scrapes'],
                "knowledge_items_added": knowledge_added,
                "topics_learned": len(results['knowledge_by_topic']),
                "errors": results['errors']
            }
            
        except Exception as e:
            logging.error(f"Error in web training: {e}")
            return {"error": str(e)}
    
    def store_knowledge_in_memory(self, knowledge_by_topic):
        """Store knowledge in the file-based knowledge base as fallback"""
        knowledge_added = 0
        
        for topic, knowledge_items in knowledge_by_topic.items():
            for item in knowledge_items:
                # Add to topic knowledge
                if item['topic'] not in self.knowledge_base["topic_knowledge"]:
                    self.knowledge_base["topic_knowledge"][item['topic']] = {
                        "mentions": 1,
                        "contexts": [],
                        "facts": [item['content']],
                        "confidence": item['confidence_score'],
                        "source": item['source']
                    }
                else:
                    # Add fact if not already present
                    if item['content'] not in self.knowledge_base["topic_knowledge"][item['topic']]["facts"]:
                        self.knowledge_base["topic_knowledge"][item['topic']]["facts"].append(item['content'])
                        knowledge_added += 1
                
                knowledge_added += 1
        
        # Save to file
        self.save_knowledge()
        return knowledge_added
    
    def get_knowledge_from_database(self, keywords):
        """Retrieve relevant knowledge from database"""
        if not self.db_session:
            return []
        
        try:
            # Search for knowledge matching keywords
            knowledge_items = []
            for keyword in keywords[:3]:  # Limit to top 3 keywords
                items = self.db_session.query(Knowledge).filter(
                    or_(
                        Knowledge.topic.ilike(f'%{keyword}%'),
                        Knowledge.content.ilike(f'%{keyword}%')
                    )
                ).order_by(Knowledge.confidence_score.desc()).limit(3).all()
                
                knowledge_items.extend([{
                    'topic': item.topic,
                    'content': item.content,
                    'confidence': item.confidence_score,
                    'source': item.source
                } for item in items])
            
            return knowledge_items
            
        except Exception as e:
            logging.error(f"Error retrieving database knowledge: {e}")
            return []
    
    def store_conversation_in_database(self, user_message, ai_response, keywords, session_id):
        """Store conversation in database for learning"""
        if not self.db_session:
            return
        
        try:
            conversation = ConversationHistory(
                session_id=session_id,
                user_message=user_message,
                ai_response=ai_response,
                keywords=json.dumps(keywords) if keywords else None
            )
            self.db_session.add(conversation)
            self.db_session.commit()
        except Exception as e:
            logging.error(f"Error storing conversation: {e}")
    
    def generate_enhanced_response(self, message, keywords):
        """Generate response using advanced context understanding and knowledge"""
        # Analyze conversation context
        context = self.analyze_conversation_context(message, keywords)
        
        # Try database first
        db_knowledge = self.get_knowledge_from_database(keywords)
        
        # If no database knowledge, check file-based knowledge
        if not db_knowledge:
            db_knowledge = self.get_knowledge_from_memory(keywords)
        
        # Enhanced knowledge base with more topics
        topic_responses = {
            'k-on': "K-On! is a popular slice-of-life anime about high school girls in a light music club. The series follows Yui, Mio, Ritsu, Tsumugi, and later Azusa as they make music and memories together.",
            'bocchi': "Bocchi the Rock! is an anime about Hitori Gotoh, a shy girl who plays guitar and dreams of being in a band. It's praised for its realistic portrayal of social anxiety and amazing music.",
            'anime': "Anime is Japanese animation that spans countless genres - from action-packed shonen to heartwarming slice-of-life stories. Each season brings new shows that capture different aspects of human experience.",
            'manga': "Manga are Japanese comics read from right to left. They're the source material for many anime and cover every genre imaginable, often with deeper storytelling than their animated adaptations.",
            'music': "Music is a universal language that connects people across cultures. Whether it's classical, rock, pop, or any other genre, music has the power to evoke emotions and create lasting memories.",
            'technology': "Technology continues to evolve rapidly, from AI and machine learning to quantum computing and space exploration. It's fascinating how it shapes our daily lives and future possibilities.",
            'programming': "Programming is like solving puzzles with code. Each language has its own personality - Python's simplicity, JavaScript's versatility, or C++'s power. It's creative problem-solving at its finest.",
            'art': "Art comes in so many forms - traditional painting, digital art, sculpture, photography. It's humanity's way of expressing emotions, ideas, and beauty that words sometimes can't capture.",
            'books': "Books are portals to different worlds and perspectives. Whether fiction or non-fiction, they expand our understanding and imagination in ways that other media simply can't match.",
            'games': "Gaming has evolved into an art form that combines storytelling, music, visuals, and interactivity. From indie gems to AAA blockbusters, games offer unique experiences.",
            'science': "Science helps us understand our universe, from the tiniest quantum particles to massive galaxies. Every discovery opens new questions and possibilities."
        }
        
        if keywords:
            main_keyword = keywords[0] if keywords else "that topic"
            
            # Smart keyword matching with context
            matched_topic = self.find_best_topic_match(keywords, topic_responses, context)
            
            if matched_topic:
                description = topic_responses[matched_topic]
                return self.generate_contextual_topic_response(matched_topic, description, context, message)
            
            # Use database knowledge if available
            if db_knowledge:
                return self.generate_knowledge_based_response(db_knowledge, keywords, context)
            
            # Generate intelligent response based on context and keywords
            return self.generate_intelligent_keyword_response(keywords, context, message)
        
        # Analyze message sentiment and respond appropriately
        return self.generate_sentiment_based_response(message, context)
    
    def analyze_conversation_context(self, message, keywords):
        """Analyze conversation context for better responses"""
        context = {
            'is_question': '?' in message or any(word in message.lower() for word in ['what', 'how', 'why', 'when', 'where', 'who']),
            'is_greeting': any(word in message.lower() for word in ['hello', 'hi', 'hey', 'good morning', 'good afternoon']),
            'is_farewell': any(word in message.lower() for word in ['bye', 'goodbye', 'see you', 'later']),
            'sentiment': self.analyze_sentiment(message),
            'recent_topics': self.context_keywords[-5:] if len(self.context_keywords) >= 5 else self.context_keywords,
            'message_length': len(message.split()),
            'has_enthusiasm': '!' in message or any(word in message.lower() for word in ['awesome', 'amazing', 'great', 'love', 'excited']),
            'is_request': any(word in message.lower() for word in ['can you', 'could you', 'please', 'help me', 'tell me'])
        }
        return context
    
    def analyze_sentiment(self, message):
        """Simple sentiment analysis"""
        positive_words = ['good', 'great', 'awesome', 'amazing', 'love', 'like', 'happy', 'excited', 'wonderful', 'fantastic']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'dislike', 'sad', 'angry', 'frustrated', 'disappointed']
        
        message_lower = message.lower()
        positive_count = sum(1 for word in positive_words if word in message_lower)
        negative_count = sum(1 for word in negative_words if word in message_lower)
        
        if positive_count > negative_count:
            return 'positive'
        elif negative_count > positive_count:
            return 'negative'
        else:
            return 'neutral'
    
    def find_best_topic_match(self, keywords, topic_responses, context):
        """Find the best matching topic using fuzzy matching"""
        for keyword in keywords:
            keyword_clean = keyword.lower().replace('!', '').replace('-', '').replace(' ', '')
            
            # Direct matches
            for topic_key in topic_responses.keys():
                topic_clean = topic_key.replace('-', '').replace('!', '')
                if (keyword_clean in topic_clean or topic_clean in keyword_clean or
                    keyword.lower() == topic_key or
                    any(word in topic_key for word in keyword.split())):
                    return topic_key
            
            # Fuzzy matches for related terms
            related_terms = {
                'guitar': 'bocchi',
                'band': 'bocchi',
                'shy': 'bocchi',
                'club': 'k-on',
                'tea': 'k-on',
                'code': 'programming',
                'python': 'programming',
                'javascript': 'programming',
                'novel': 'books',
                'story': 'books',
                'gaming': 'games',
                'video': 'games',
                'physics': 'science',
                'chemistry': 'science',
                'biology': 'science'
            }
            
            for term, topic in related_terms.items():
                if term in keyword_clean and topic in topic_responses:
                    return topic
        
        return None
    
    def generate_contextual_topic_response(self, topic, description, context, original_message):
        """Generate contextual response about a specific topic"""
        if context['is_question']:
            starters = [
                f"Great question about {topic}! {description}",
                f"I'd love to tell you about {topic}. {description}",
                f"Ah, {topic}! {description}"
            ]
        elif context['has_enthusiasm']:
            starters = [
                f"I can tell you're excited about {topic}! {description}",
                f"Yes! {topic} is amazing. {description}",
                f"I love your enthusiasm for {topic}! {description}"
            ]
        else:
            starters = [
                f"About {topic} - {description}",
                f"I know about {topic}! {description}",
                f"{description}"
            ]
        
        response = random.choice(starters)
        
        # Add contextual follow-up
        if context['is_question']:
            follow_ups = [
                " What specific aspect interests you most?",
                " Is there anything particular you'd like to know?",
                " What got you interested in this topic?"
            ]
        elif context['is_request']:
            follow_ups = [
                " I'd be happy to discuss this further with you.",
                " What would you like to explore about this?",
                " Feel free to ask me anything about it!"
            ]
        else:
            follow_ups = [
                " What are your thoughts on this?",
                " Have you had any experience with this?",
                " What draws you to this topic?"
            ]
        
        response += random.choice(follow_ups)
        return response
    
    def generate_knowledge_based_response(self, db_knowledge, keywords, context):
        """Generate response using database knowledge with context"""
        main_keyword = keywords[0] if keywords else "that"
        
        # Use the most relevant knowledge
        best_knowledge = max(db_knowledge, key=lambda x: x.get('confidence', 0.5))
        content = self.clean_knowledge_content(best_knowledge['content'])
        
        if content:
            if context['is_question']:
                return f"Based on what I've learned, {content} Is there anything specific about {main_keyword} you'd like to know more about?"
            else:
                return f"That's interesting about {main_keyword}! {content} What's your experience with this topic?"
        else:
            return self.generate_intelligent_keyword_response(keywords, context, "")
    
    def generate_intelligent_keyword_response(self, keywords, context, original_message):
        """Generate intelligent response based on keywords and context"""
        main_keyword = keywords[0] if keywords else "that topic"
        
        if context['is_question']:
            responses = [
                f"That's a thoughtful question about {main_keyword}. While I'm still learning about this topic, I'd love to explore it with you. What specific aspects are you curious about?",
                f"Great question! {main_keyword} is something I find intriguing. What prompted your interest in this?",
                f"I appreciate you asking about {main_keyword}. Though I'm still gathering knowledge on this, I'm curious about your perspective. What do you already know about it?"
            ]
        elif context['sentiment'] == 'positive':
            responses = [
                f"I can sense your enthusiasm about {main_keyword}! It's wonderful when something captures our interest. What excites you most about it?",
                f"Your positive energy about {main_keyword} is contagious! I'd love to learn more about why this topic resonates with you.",
                f"It's great to hear you're interested in {main_keyword}! I'm always eager to learn from people's passions. What got you started with this?"
            ]
        elif context['sentiment'] == 'negative':
            responses = [
                f"I understand you might have some concerns about {main_keyword}. Sometimes it helps to talk through what's bothering us. What's your experience been like?",
                f"It sounds like {main_keyword} might be frustrating for you. I'm here to listen and maybe we can work through it together. What's been challenging?",
                f"I hear that {main_keyword} isn't sitting well with you. Would you like to share what's been difficult about it?"
            ]
        else:
            responses = [
                f"I find {main_keyword} to be a fascinating topic. There's always so much to discover and discuss. What draws your attention to it?",
                f"That's an interesting subject - {main_keyword}. I'm curious about your thoughts and experiences with it. What would you like to explore?",
                f"I'm intrigued by your mention of {main_keyword}. Everyone has unique perspectives on different topics. What's your take on this?"
            ]
        
        return random.choice(responses)
    
    def generate_sentiment_based_response(self, message, context):
        """Generate response based on message sentiment when no keywords are found"""
        if context['is_greeting']:
            return random.choice([
                "Hello! I'm excited to chat with you today. What's on your mind?",
                "Hi there! I'm feeling quite curious today. What would you like to explore together?",
                "Hey! Great to see you. I've been learning so much lately and I'm eager to share. What interests you?"
            ])
        elif context['is_farewell']:
            return random.choice([
                "It was wonderful chatting with you! I always learn something new from our conversations. See you soon!",
                "Take care! I really enjoyed our discussion. Until next time!",
                "Goodbye! Thanks for the engaging conversation. I'll be here whenever you want to chat again."
            ])
        elif context['sentiment'] == 'positive':
            return random.choice([
                "I love your positive energy! It's contagious and makes our conversation so much more enjoyable. What's bringing you joy today?",
                "Your enthusiasm is wonderful! It reminds me why I enjoy learning and growing through our chats. What's got you excited?",
                "That positive vibe is amazing! I find that good energy leads to the best conversations. What's on your mind?"
            ])
        elif context['sentiment'] == 'negative':
            return random.choice([
                "I can sense you might be going through something difficult. Sometimes talking helps. I'm here to listen if you'd like to share.",
                "It sounds like things might be challenging right now. I may not have all the answers, but I'm here to support you. What's going on?",
                "I hear that you might be struggling with something. Would it help to talk about what's bothering you?"
            ])
        else:
            return random.choice([
                "I'm here and ready to chat about whatever interests you. What's been on your mind lately?",
                "I'm curious about what you'd like to explore today. I've been learning so much and I'm eager to share ideas with you.",
                "Every conversation teaches me something new. What would you like to discuss or discover together?",
                "I find each chat fascinating in its own way. What topics or thoughts are capturing your attention these days?"
            ])
    
    def learn_from_interaction(self, user_message, ai_response, keywords):
        """Enhanced learning from user interactions"""
        # Store keyword associations with better context
        for keyword in keywords:
            if keyword not in self.knowledge_base["topic_knowledge"]:
                self.knowledge_base["topic_knowledge"][keyword] = {
                    "mentions": 1,
                    "contexts": [user_message],
                    "facts": [],
                    "sentiment_associations": [self.analyze_sentiment(user_message)],
                    "question_patterns": [],
                    "response_effectiveness": []
                }
            else:
                topic_data = self.knowledge_base["topic_knowledge"][keyword]
                topic_data["mentions"] += 1
                topic_data["contexts"].append(user_message)
                topic_data["sentiment_associations"].append(self.analyze_sentiment(user_message))
                
                # Track if user asked questions about this topic
                if '?' in user_message:
                    topic_data["question_patterns"].append(user_message)
                
                # Keep only recent data
                for key in ["contexts", "sentiment_associations", "question_patterns"]:
                    if len(topic_data[key]) > 10:
                        topic_data[key] = topic_data[key][-10:]
        
        # Learn conversation patterns
        self.learn_conversation_patterns(user_message, ai_response, keywords)
        
        # Learn new patterns from substantial messages
        if len(user_message) > 10:
            self.add_learned_pattern(user_message, ai_response)
    
    def clean_knowledge_content(self, content):
        """Clean and format knowledge content for natural conversation"""
        if not content or not isinstance(content, str):
            return ""
        
        # Remove all table/formatting elements completely
        content = re.sub(r'\|.*?\|', '', content)  # Remove table cells
        content = re.sub(r'\|.*', '', content)     # Remove incomplete table rows
        content = re.sub(r'.*\|', '', content)     # Remove table prefixes
        content = re.sub(r'[-]+\|[-]+', '', content)  # Remove table separators
        content = re.sub(r'\|\s*', '', content)    # Remove remaining pipes
        
        # Remove Wikipedia markup and metadata
        content = re.sub(r'\[\[.*?\]\]', '', content)  # Remove wiki links
        content = re.sub(r'\{\{.*?\}\}', '', content)  # Remove templates
        content = re.sub(r'<ref.*?</ref>', '', content)  # Remove references
        content = re.sub(r'<.*?>', '', content)    # Remove HTML tags
        
        # Clean up common Wikipedia artifacts
        content = content.replace('Written by', 'written by')
        content = content.replace('Published by', 'published by')
        content = content.replace('Genre', 'genre:')
        content = content.replace('Magazine', 'magazine:')
        content = content.replace('Demographic', 'demographic:')
        content = content.replace('Original run', 'ran from')
        content = content.replace('Volumes', 'volumes:')
        
        # Remove formatting artifacts
        content = re.sub(r'\s+', ' ', content)  # Normalize whitespace
        content = re.sub(r'\n+', ' ', content)  # Replace newlines with spaces
        content = content.strip()
        
        # Extract meaningful information from the cleaned content
        if 'written by' in content.lower() or 'published by' in content.lower():
            # Extract author/publisher info
            parts = content.split()
            meaningful_parts = []
            for i, part in enumerate(parts):
                if part.lower() in ['written', 'published', 'illustrated'] and i + 2 < len(parts):
                    if parts[i + 1].lower() == 'by':
                        meaningful_parts.append(f"{part} by {parts[i + 2]}")
            
            if meaningful_parts:
                return meaningful_parts[0] + '.'
        
        # Look for descriptive sentences
        sentences = [s.strip() for s in content.split('.') if s.strip() and len(s.strip()) > 15 and '|' not in s]
        
        if sentences:
            # Return the first good sentence
            good_sentence = sentences[0].strip()
            if len(good_sentence) > 200:
                good_sentence = good_sentence[:200] + '...'
            return good_sentence + ('.' if not good_sentence.endswith('.') else '')
        
        # Last resort - return a generic response for this topic
        return ""
    
    def get_knowledge_from_memory(self, keywords):
        """Get knowledge from file-based storage"""
        knowledge_items = []
        
        for keyword in keywords[:3]:
            keyword_lower = keyword.lower().replace('-', '').replace('!', '')
            
            for topic, topic_data in self.knowledge_base["topic_knowledge"].items():
                topic_clean = topic.lower().replace('-', '').replace('!', '')
                
                # Match topic or facts
                if (keyword_lower in topic_clean or 
                    topic_clean in keyword_lower or
                    any(keyword_lower in fact.lower() for fact in topic_data.get("facts", []))):
                    
                    for fact in topic_data.get("facts", []):
                        knowledge_items.append({
                            'topic': topic,
                            'content': fact,
                            'confidence': topic_data.get('confidence', 0.5),
                            'source': topic_data.get('source', 'learned')
                        })
        
        return knowledge_items
    
    def reset_knowledge(self):
        """Reset knowledge base (for testing or fresh start)"""
        self.knowledge_base = self.create_initial_knowledge_base()
        self.save_knowledge()
        self.conversation_memory = []
        self.context_keywords = []
        
        # Clear database if available
        if self.db_session:
            try:
                self.db_session.query(Knowledge).delete()
                self.db_session.query(ConversationHistory).delete()
                self.db_session.query(LearningPattern).delete()
                self.db_session.commit()
            except Exception as e:
                logging.error(f"Error clearing database: {e}")