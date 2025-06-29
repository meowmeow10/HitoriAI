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
                    "facts": [],
                    "sentiment_associations": [self.analyze_sentiment(user_message)],
                    "question_patterns": [],
                    "response_effectiveness": []
                }
            else:
                topic_data = self.knowledge_base["topic_knowledge"][keyword]
                topic_data["mentions"] += 1
                topic_data["contexts"].append(user_message)
                
                # Ensure all required fields exist
                if "sentiment_associations" not in topic_data:
                    topic_data["sentiment_associations"] = []
                if "question_patterns" not in topic_data:
                    topic_data["question_patterns"] = []
                if "response_effectiveness" not in topic_data:
                    topic_data["response_effectiveness"] = []
                
                topic_data["sentiment_associations"].append(self.analyze_sentiment(user_message))
                
                # Track if user asked questions about this topic
                if '?' in user_message:
                    topic_data["question_patterns"].append(user_message)
                
                # Keep only recent data
                for key in ["contexts", "sentiment_associations", "question_patterns"]:
                    if len(topic_data[key]) > 10:
                        topic_data[key] = topic_data[key][-10:]
        
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
            # Search for knowledge matching keywords - limit to prevent overly long responses
            knowledge_items = []
            for keyword in keywords[:2]:  # Limit to top 2 keywords
                items = self.db_session.query(Knowledge).filter(
                    or_(
                        Knowledge.topic.ilike(f'%{keyword}%'),
                        Knowledge.content.ilike(f'%{keyword}%')
                    )
                ).order_by(Knowledge.confidence_score.desc()).limit(2).all()  # Limit to 2 items per keyword
                
                knowledge_items.extend([{
                    'topic': item.topic,
                    'content': item.content,
                    'confidence': item.confidence_score,
                    'source': item.source
                } for item in items])
            
            # Return only the top 3 most relevant items
            return sorted(knowledge_items, key=lambda x: x.get('confidence', 0.5), reverse=True)[:3]
            
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
        
        # Check for conversation history to avoid repetition
        recent_responses = [entry.get('ai', '') for entry in self.conversation_memory[-5:] if 'ai' in entry]
        
        # Try database first
        db_knowledge = self.get_knowledge_from_database(keywords)
        
        # If no database knowledge, check file-based knowledge
        if not db_knowledge:
            db_knowledge = self.get_knowledge_from_memory(keywords)
        
        # If still no knowledge and we have keywords, try Wikipedia search
        if not db_knowledge and keywords and context.get('is_question'):
            wikipedia_knowledge = self.search_wikipedia_for_keywords(keywords)
            if wikipedia_knowledge:
                db_knowledge = wikipedia_knowledge
        
        # Add joke telling capability
        if any(word in message.lower() for word in ['joke', 'funny', 'humor', 'laugh', 'tell me something funny']):
            return self.tell_joke(keywords, context)
        
        # Add code writing capability
        if any(word in message.lower() for word in ['code', 'program', 'write code', 'programming', 'function', 'script']):
            return self.help_with_coding(message, keywords, context)
        
        # Enhanced knowledge base with more varied responses
        topic_responses = {
            'vr': [
                "VR headsets are absolutely fascinating! They create immersive virtual worlds by tracking your head movements and displaying stereoscopic images. Modern VR headsets like the Meta Quest, PlayStation VR, and Valve Index offer incredible experiences - from exploring virtual worlds to playing immersive games. What interests you most about VR technology? Are you thinking about getting one, or curious about how they work?",
                "Virtual Reality is such an exciting field! VR headsets transport you to completely different worlds using advanced display technology, motion tracking, and spatial audio. They're used for gaming, education, training simulations, and even therapy. The technology has come so far - we now have wireless headsets with hand tracking! What aspect of VR fascinates you most?",
                "VR headsets are incredible pieces of technology! They use multiple sensors, high-resolution displays, and precise tracking to create the illusion that you're somewhere else entirely. From exploring ancient civilizations to practicing surgery, VR opens up amazing possibilities. Have you tried VR before, or are you curious about what it's like?"
            ],
            'headset': [
                "Headsets come in so many varieties! There are VR headsets for virtual reality, gaming headsets for immersive audio, and professional headsets for work calls. Each type is engineered for specific purposes - VR headsets focus on visual immersion and tracking, while gaming headsets prioritize audio quality and comfort for long sessions. What type of headset are you interested in?",
                "The world of headsets is diverse and exciting! From lightweight wireless earbuds to heavy-duty professional broadcasting headsets, each serves different needs. Gaming headsets often feature surround sound and noise cancellation, while VR headsets include motion sensors and high-resolution displays. Are you looking for recommendations, or curious about how they work?"
            ],
            'pepsi': [
                "Pepsi has quite a history! It was created in 1893 by pharmacist Caleb Bradham. Interesting how it became Coca-Cola's main rival.",
                "The Cola Wars between Pepsi and Coke were fascinating! Remember the Pepsi Challenge campaigns?",
                "Pepsi's marketing has always been bold - from the 'Pepsi Generation' to celebrity endorsements. What do you think of their approach?",
                "Did you know Pepsi once briefly owned a fleet of Soviet warships? Wild business deals in the 80s!"
            ],
            'coke': [
                "Coca-Cola is the classic! That secret formula has been kept under wraps for over a century.",
                "The polar bear ads and 'Share a Coke' campaigns were genius marketing moves.",
                "Coke's global reach is incredible - it's available in almost every country on Earth."
            ],
            'drinks': [
                "There are so many interesting beverages out there! From artisanal sodas to energy drinks to traditional teas.",
                "The beverage industry is always innovating - have you tried any unique flavors lately?",
                "I find it fascinating how different cultures have their own signature drinks."
            ],
            'k-on': "K-On! is such a delightful slice-of-life anime! It follows five high school girls in their light music club - Yui, Mio, Ritsu, Tsumugi, and Azusa. The show perfectly captures the joy of friendship and music-making.",
            'bocchi': "Bocchi the Rock! is absolutely fantastic! It tells the story of Hitori Gotoh, a socially anxious guitarist who joins a band. The series brilliantly portrays social anxiety while celebrating the power of music and friendship.",
            'anime': "Anime is such a rich medium! From epic adventures like Attack on Titan to heartwarming stories like Your Name, there's something for everyone. What genres do you enjoy most?",
            'music': "Music truly is magical! It can instantly transport you to different emotions and memories. Whether it's a catchy pop song or a moving classical piece, music speaks to the soul.",
            'technology': "Technology is evolving at an incredible pace! From AI assistants like me to quantum computers and space exploration, we're living in exciting times. What tech interests you most?",
            'hello': "Hello there! I'm excited to chat with you today. What's on your mind?",
            'help': "I'd love to help you with whatever you need! Whether it's answering questions, having a conversation, or exploring topics together, I'm here for you."
        }
        
        if keywords:
            main_keyword = keywords[0] if keywords else "that topic"
            
            # Smart keyword matching with context
            matched_topic = self.find_best_topic_match(keywords, topic_responses, context)
            
            if matched_topic:
                response = self.select_varied_response(matched_topic, topic_responses, recent_responses, context, message)
                if response:
                    return response
            
            # Use database knowledge if available
            if db_knowledge:
                return self.generate_knowledge_based_response(db_knowledge, keywords, context, recent_responses)
            
            # Generate intelligent response based on context and keywords
            return self.generate_intelligent_keyword_response(keywords, context, message, recent_responses)
        
        # Analyze message sentiment and respond appropriately
        return self.generate_sentiment_based_response(message, context, recent_responses)
    
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
    
    def generate_knowledge_based_response(self, db_knowledge, keywords, context, recent_responses=None):
        """Generate response using database knowledge with context"""
        if recent_responses is None:
            recent_responses = []
            
        main_keyword = keywords[0] if keywords else "that"
        
        # Use the most relevant knowledge
        best_knowledge = max(db_knowledge, key=lambda x: x.get('confidence', 0.5))
        content = self.clean_knowledge_content(best_knowledge['content'])
        
        if content:
            if context['is_question']:
                response_templates = [
                    f"Based on what I've learned, {content} What else would you like to know about {main_keyword}?",
                    f"From my knowledge, {content} Any other questions about {main_keyword}?",
                    f"Here's what I know: {content} What interests you most about {main_keyword}?"
                ]
            else:
                response_templates = [
                    f"That's interesting about {main_keyword}! {content} What's your experience with this topic?",
                    f"Ah, {main_keyword}! {content} What do you think about that?",
                    f"I know a bit about {main_keyword}. {content} How does that relate to your interest?"
                ]
            
            # Select response that's not too similar to recent ones
            for template in response_templates:
                if not any(self.responses_too_similar(template, recent) for recent in recent_responses):
                    return template
            
            return response_templates[0]  # Fallback to first if all are similar
        else:
            return self.generate_intelligent_keyword_response(keywords, context, "", recent_responses)
    
    def generate_intelligent_keyword_response(self, keywords, context, original_message, recent_responses=None):
        """Generate intelligent response based on keywords and context"""
        if recent_responses is None:
            recent_responses = []
            
        main_keyword = keywords[0] if keywords else "that topic"
        
        # Check if we have learned about this keyword before
        has_knowledge = main_keyword in self.knowledge_base["topic_knowledge"]
        
        if context['is_question']:
            if has_knowledge:
                topic_data = self.knowledge_base["topic_knowledge"][main_keyword]
                if topic_data.get("facts"):
                    fact = random.choice(topic_data["facts"])
                    return f"Great question about {main_keyword}! {fact} What else would you like to know about it?"
            
            responses = [
                f"That's a fascinating question about {main_keyword}! Let me share what I know and learn from your perspective too. {main_keyword} is a topic with many interesting aspects - from its history and development to its current applications and future potential. What specific aspects are you most curious about? Are you looking to understand how it works, its impact, or perhaps personal experiences with it?",
                f"Great question about {main_keyword}! I love exploring topics like this because there's always so much depth to discover. Whether we're talking about the technical side, the human stories behind it, or its broader implications, {main_keyword} offers rich discussion material. What prompted your curiosity about this particular topic? I'd love to hear your thoughts and share what I've learned!",
                f"Excellent question! {main_keyword} is definitely worth diving deep into. I find that the best conversations happen when we can explore topics from multiple angles - the facts, the personal connections, the 'why it matters' aspects. What drew you to ask about {main_keyword}? Do you have any experience with it, or is this completely new territory you're exploring?",
                f"You've touched on something really interesting with {main_keyword}! I always enjoy when conversations go in unexpected directions like this. There's often more to explore than meets the eye initially. What angle interests you most? Are you thinking about it from a practical standpoint, or are you more curious about the bigger picture and implications?",
                f"That's a topic worth exploring thoroughly! {main_keyword} is one of those subjects where every question leads to more fascinating discoveries. I find that understanding the 'why' behind things is often as interesting as the 'what' and 'how'. What made you think of {main_keyword}? Let's dive into whatever aspect interests you most!"
            ]
        elif context['sentiment'] == 'positive':
            responses = [
                f"I can tell you're excited about {main_keyword}! Your enthusiasm is infectious. What makes this topic so interesting to you?",
                f"I love your positive energy about {main_keyword}! It's clear this resonates with you. What got you interested in it?",
                f"Your excitement about {main_keyword} is wonderful! I'd love to hear what draws you to this topic.",
                f"Your enthusiasm for {main_keyword} is great! What's the most exciting aspect for you?",
                f"I can feel your passion for {main_keyword}! What sparked this interest?"
            ]
        elif context['sentiment'] == 'negative':
            responses = [
                f"I sense you might have mixed feelings about {main_keyword}. Sometimes talking helps clarify our thoughts. What's your experience been?",
                f"It seems like {main_keyword} might be challenging for you. I'm here to listen. What's been difficult about it?",
                f"I understand {main_keyword} might not be sitting well with you. Would you like to share what's concerning you?",
                f"I hear some hesitation about {main_keyword}. What's been troubling you about it?",
                f"It sounds like {main_keyword} has been on your mind. Want to talk through what's bothering you?"
            ]
        else:
            # For neutral sentiment, be more engaging and conversational
            if has_knowledge:
                responses = [
                    f"Ah, {main_keyword}! That's a topic I've been learning about. What's your take on it?",
                    f"I find {main_keyword} quite fascinating. There's always more to discover. What interests you about it?",
                    f"{main_keyword} is such an interesting subject. I'm curious about your perspective on it.",
                    f"I've encountered {main_keyword} before. What's your experience with it?",
                    f"That's a topic I'm familiar with! What would you like to discuss about {main_keyword}?"
                ]
            else:
                responses = [
                    f"I'd love to learn more about {main_keyword} from you. What makes it interesting?",
                    f"That's a great topic - {main_keyword}. I'm always eager to explore new subjects. What would you like to discuss about it?",
                    f"I'm curious about {main_keyword}. Everyone has unique insights on different topics. What's yours?",
                    f"Tell me more about {main_keyword}! I'm always learning something new.",
                    f"That's intriguing! What's the story with {main_keyword}?"
                ]
        
        # Filter responses that are too similar to recent ones
        available_responses = [r for r in responses if not any(self.responses_too_similar(r, recent) for recent in recent_responses)]
        
        if available_responses:
            return random.choice(available_responses)
        else:
            # Generate a completely fresh response if all are too similar
            return f"That's an interesting topic! What would you like to explore about {main_keyword}?"
    
    def select_varied_response(self, topic, topic_responses, recent_responses, context, message):
        """Select a varied response that avoids recent repetitions"""
        if isinstance(topic_responses[topic], list):
            # Filter out responses that are too similar to recent ones
            available_responses = []
            for response in topic_responses[topic]:
                is_too_similar = False
                for recent in recent_responses:
                    if self.responses_too_similar(response, recent):
                        is_too_similar = True
                        break
                if not is_too_similar:
                    available_responses.append(response)
            
            if available_responses:
                base_response = random.choice(available_responses)
                return self.add_contextual_flourish(base_response, context, message)
            else:
                # If all responses are too similar, generate a new one
                return self.generate_fresh_response(topic, context, message)
        else:
            # Single response - add variation through context
            return self.add_contextual_flourish(topic_responses[topic], context, message)
    
    def responses_too_similar(self, response1, response2):
        """Check if two responses are too similar"""
        if not response1 or not response2:
            return False
        
        # Convert to lowercase and split into words
        words1 = set(response1.lower().split())
        words2 = set(response2.lower().split())
        
        # Calculate overlap
        overlap = len(words1.intersection(words2))
        total_unique = len(words1.union(words2))
        
        if total_unique == 0:
            return False
        
        similarity = overlap / total_unique
        return similarity > 0.6  # 60% similarity threshold
    
    def add_contextual_flourish(self, base_response, context, message):
        """Add contextual variation to a base response"""
        if context['is_question']:
            question_starters = [
                "Great question! ",
                "That's interesting you ask! ",
                "I'm glad you brought that up. ",
                ""
            ]
            base_response = random.choice(question_starters) + base_response
        
        if context['has_enthusiasm']:
            enthusiasm_enders = [
                " Your excitement is contagious!",
                " I love the enthusiasm!",
                " What got you so interested in this?",
                ""
            ]
            base_response += random.choice(enthusiasm_enders)
        elif random.choice([True, False]):
            general_enders = [
                " What's your take on this?",
                " Have you had experience with this?",
                " What interests you most about it?",
                " What would you like to know more about?",
                ""
            ]
            base_response += random.choice(general_enders)
        
        return base_response
    
    def generate_fresh_response(self, topic, context, message):
        """Generate a completely fresh response when others are too repetitive"""
        fresh_approaches = {
            'pepsi': [
                "You know, beverage history is pretty wild! What draws you to Pepsi specifically?",
                "The soft drink industry has such interesting stories. Any particular aspect you're curious about?",
                "That's a classic brand! Are you more interested in the business side or just enjoy the taste?"
            ],
            'coke': [
                "The Coca-Cola story is fascinating from a business perspective. What interests you about it?",
                "That's one of the most recognizable brands worldwide! What aspect caught your attention?"
            ]
        }
        
        if topic in fresh_approaches:
            return random.choice(fresh_approaches[topic])
        else:
            return f"I'm always learning more about {topic}. What specifically interests you about it?"
    
    def generate_sentiment_based_response(self, message, context, recent_responses=None):
        """Generate response based on message sentiment when no keywords are found"""
        if recent_responses is None:
            recent_responses = []
            
        if context['is_greeting']:
            responses = [
                "Hello! I'm excited to chat with you today. What's on your mind?",
                "Hi there! I'm feeling quite curious today. What would you like to explore together?",
                "Hey! Great to see you. I've been learning so much lately and I'm eager to share. What interests you?",
                "Hello! Ready for an interesting conversation? What would you like to talk about?"
            ]
        elif context['is_farewell']:
            responses = [
                "It was wonderful chatting with you! I always learn something new from our conversations. See you soon!",
                "Take care! I really enjoyed our discussion. Until next time!",
                "Goodbye! Thanks for the engaging conversation. I'll be here whenever you want to chat again.",
                "See you later! I appreciate our chat today."
            ]
        elif context['sentiment'] == 'positive':
            responses = [
                "I love your positive energy! It's contagious and makes our conversation so much more enjoyable. What's bringing you joy today?",
                "Your enthusiasm is wonderful! It reminds me why I enjoy learning and growing through our chats. What's got you excited?",
                "That positive vibe is amazing! I find that good energy leads to the best conversations. What's on your mind?",
                "Your good mood is infectious! What's making you feel so positive today?"
            ]
        elif context['sentiment'] == 'negative':
            responses = [
                "I can sense you might be going through something difficult. Sometimes talking helps. I'm here to listen if you'd like to share.",
                "It sounds like things might be challenging right now. I may not have all the answers, but I'm here to support you. What's going on?",
                "I hear that you might be struggling with something. Would it help to talk about what's bothering you?",
                "I'm here to listen if you need someone to talk to. What's on your mind?"
            ]
        else:
            responses = [
                "I'm here and ready to chat about whatever interests you. What's been on your mind lately?",
                "I'm curious about what you'd like to explore today. I've been learning so much and I'm eager to share ideas with you.",
                "Every conversation teaches me something new. What would you like to discuss or discover together?",
                "I find each chat fascinating in its own way. What topics or thoughts are capturing your attention these days?",
                "What's interesting you today? I'm always up for a good conversation."
            ]
        
        # Filter out responses too similar to recent ones
        available_responses = [r for r in responses if not any(self.responses_too_similar(r, recent) for recent in recent_responses)]
        
        if available_responses:
            return random.choice(available_responses)
        else:
            return "I'm here and ready to chat! What would you like to talk about?"
    
    
    
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
        content = re.sub(r'\[\d+\]', '', content)  # Remove reference numbers like [13]
        
        # Remove formatting artifacts
        content = re.sub(r'\s+', ' ', content)  # Normalize whitespace
        content = re.sub(r'\n+', ' ', content)  # Replace newlines with spaces
        content = content.strip()
        
        # Look for meaningful sentences - be more careful about sentence boundaries
        sentences = []
        for sentence in content.split('.'):
            sentence = sentence.strip()
            # Filter out short fragments, table remnants, and reference artifacts
            if (len(sentence) > 20 and 
                '|' not in sentence and 
                not re.match(r'^\d+$', sentence) and  # Skip lone numbers
                not sentence.startswith('[') and      # Skip reference markers
                len(sentence.split()) > 3):           # Must have at least 4 words
                sentences.append(sentence)
        
        if sentences:
            # Build result with better length management
            result_sentences = []
            total_length = 0
            max_length = 250  # Reduced to ensure complete sentences
            
            for sentence in sentences[:2]:  # Limit to 2 sentences max
                sentence_with_period = sentence + '.'
                # Only add if it doesn't exceed our limit
                if total_length + len(sentence_with_period) + 1 <= max_length:
                    result_sentences.append(sentence)
                    total_length += len(sentence_with_period) + 1
                else:
                    break
            
            if result_sentences:
                result = '. '.join(result_sentences) + '.'
                return result
        
        # If no good sentences found, return empty to use fallback responses
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
    
    def search_wikipedia_for_keywords(self, keywords):
        """Search Wikipedia for unknown keywords and extract knowledge"""
        try:
            if not self.web_scraper:
                # Create a simple scraper even without database
                from web_scraper import WebKnowledgeScraper
                simple_scraper = WebKnowledgeScraper(None)
            else:
                simple_scraper = self.web_scraper
            
            knowledge_items = []
            
            # Try each keyword on Wikipedia
            for keyword in keywords[:2]:  # Limit to 2 keywords to avoid too many requests
                # Clean keyword for Wikipedia URL
                clean_keyword = keyword.replace(' ', '_').replace('!', '%21')
                wikipedia_url = f'https://en.wikipedia.org/wiki/{clean_keyword}'
                
                try:
                    # Scrape Wikipedia page
                    result = simple_scraper.scrape_url(wikipedia_url)
                    
                    if result['success'] and result['knowledge_items']:
                        # Store knowledge for future use
                        for item in result['knowledge_items'][:3]:  # Limit to 3 facts per keyword
                            knowledge_items.append({
                                'topic': item['topic'],
                                'content': item['content'],
                                'confidence': item['confidence_score'],
                                'source': f'wikipedia:{wikipedia_url}'
                            })
                            
                            # Also store in memory for future use
                            self.store_learned_knowledge(item['topic'], item['content'], item['confidence_score'], wikipedia_url)
                        
                        # If we found good knowledge, break to avoid too much info
                        if len(knowledge_items) >= 2:
                            break
                            
                except Exception as e:
                    logging.debug(f"Could not fetch Wikipedia page for {keyword}: {e}")
                    continue
            
            return knowledge_items if knowledge_items else None
            
        except Exception as e:
            logging.error(f"Error in Wikipedia search: {e}")
            return None
    
    def tell_joke(self, keywords=None, context=None):
        """Tell jokes based on context or randomly"""
        tech_jokes = [
            "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
            "How many programmers does it take to change a light bulb? None, that's a hardware problem! 💡",
            "Why do Java developers wear glasses? Because they can't C#! 👓",
            "A SQL query goes into a bar, walks up to two tables and asks... 'Can I join you?' 🍺",
            "Why don't programmers like nature? It has too many bugs! 🌿🐛",
            "There are only 10 types of people in the world: those who understand binary and those who don't! 😄"
        ]
        
        general_jokes = [
            "Why don't scientists trust atoms? Because they make up everything! ⚛️",
            "I told my wife she was drawing her eyebrows too high. She looked surprised! 😮",
            "Why don't eggs tell jokes? They'd crack each other up! 🥚😂",
            "What do you call a fake noodle? An impasta! 🍝",
            "Why did the scarecrow win an award? He was outstanding in his field! 🌾",
            "What's the best thing about Switzerland? I don't know, but the flag is a big plus! 🇨🇭➕"
        ]
        
        ai_jokes = [
            "Why did the AI go to therapy? It had too many deep learning issues! 🤖",
            "What do you call an AI that sings? A neural network! 🎵",
            "Why don't robots ever panic? They have excellent processing power! 💻",
            "What's an AI's favorite type of music? Algo-rhythms! 🎶"
        ]
        
        # Select joke category based on keywords
        if keywords and any(word in ['code', 'program', 'tech', 'computer'] for word in keywords):
            jokes = tech_jokes
        elif keywords and any(word in ['ai', 'robot', 'artificial'] for word in keywords):
            jokes = ai_jokes
        else:
            jokes = general_jokes
        
        joke = random.choice(jokes)
        follow_ups = [
            " Hope that made you smile! Want to hear another one?",
            " Did that get a chuckle? I've got more where that came from! 😄",
            " Laughter is the best debugging tool! Want another joke?",
            " Comedy is all about timing... and good material! What else can I help you with?"
        ]
        
        return joke + random.choice(follow_ups)
    
    def help_with_coding(self, message, keywords=None, context=None):
        """Help with coding questions and requests"""
        message_lower = message.lower()
        
        # Detect programming language
        languages = {
            'python': ['python', 'py', 'django', 'flask'],
            'javascript': ['javascript', 'js', 'node', 'react', 'vue'],
            'java': ['java'],
            'c++': ['c++', 'cpp'],
            'html': ['html', 'web'],
            'css': ['css', 'style'],
            'sql': ['sql', 'database']
        }
        
        detected_lang = None
        for lang, terms in languages.items():
            if any(term in message_lower for term in terms):
                detected_lang = lang
                break
        
        # Generate code examples based on request
        if 'function' in message_lower or 'def' in message_lower:
            return self.generate_function_example(detected_lang, keywords)
        elif 'loop' in message_lower:
            return self.generate_loop_example(detected_lang)
        elif 'class' in message_lower:
            return self.generate_class_example(detected_lang)
        elif 'hello world' in message_lower:
            return self.generate_hello_world(detected_lang)
        else:
            return self.generate_general_coding_help(detected_lang, message, keywords)
    
    def generate_function_example(self, language, keywords=None):
        """Generate function examples"""
        if language == 'python':
            return """Here's a Python function example:

```python
def calculate_factorial(n):
    \"\"\"Calculate factorial of a number\"\"\"
    if n <= 1:
        return 1
    return n * calculate_factorial(n - 1)

# Usage
result = calculate_factorial(5)
print(f"5! = {result}")  # Output: 5! = 120
```

This function uses recursion to calculate factorials. Want to see examples in other languages or different types of functions?"""
        
        elif language == 'javascript':
            return """Here's a JavaScript function example:

```javascript
function greetUser(name, time = 'day') {
    return `Hello ${name}, have a great ${time}!`;
}

// Usage
console.log(greetUser('Alice'));         // "Hello Alice, have a great day!"
console.log(greetUser('Bob', 'evening')); // "Hello Bob, have a great evening!"
```

This shows function parameters with default values. Need help with arrow functions or async functions?"""
        
        else:
            return "I can help you write functions! Which programming language are you working with? I can provide examples in Python, JavaScript, Java, C++, and more. What specific type of function do you need help with?"
    
    def generate_loop_example(self, language):
        """Generate loop examples"""
        if language == 'python':
            return """Here are Python loop examples:

```python
# For loop with range
for i in range(5):
    print(f"Count: {i}")

# For loop with list
fruits = ['apple', 'banana', 'orange']
for fruit in fruits:
    print(f"I like {fruit}")

# While loop
count = 0
while count < 3:
    print(f"While loop: {count}")
    count += 1

# List comprehension (Pythonic way)
squares = [x**2 for x in range(5)]
print(squares)  # [0, 1, 4, 9, 16]
```

Python loops are very readable and powerful! Need help with specific loop scenarios?"""
        
        elif language == 'javascript':
            return """Here are JavaScript loop examples:

```javascript
// For loop
for (let i = 0; i < 5; i++) {
    console.log(`Count: ${i}`);
}

// For...of loop (arrays)
const fruits = ['apple', 'banana', 'orange'];
for (const fruit of fruits) {
    console.log(`I like ${fruit}`);
}

// For...in loop (objects)
const person = {name: 'Alice', age: 30, city: 'New York'};
for (const key in person) {
    console.log(`${key}: ${person[key]}`);
}

// Array methods (functional approach)
const numbers = [1, 2, 3, 4, 5];
numbers.forEach(num => console.log(num * 2));
```

JavaScript offers many ways to iterate! Want to learn about map, filter, or reduce?"""
        
        else:
            return "I can show you loop examples! Which programming language are you using? I have examples for Python, JavaScript, Java, C++, and more. What type of loop are you trying to create?"
    
    def generate_class_example(self, language):
        """Generate class examples"""
        if language == 'python':
            return """Here's a Python class example:

```python
class Dog:
    def __init__(self, name, breed, age):
        self.name = name
        self.breed = breed
        self.age = age
        self.energy = 100
    
    def bark(self):
        print(f"{self.name} says Woof!")
        return "Woof!"
    
    def play(self):
        if self.energy > 20:
            self.energy -= 20
            print(f"{self.name} is playing! Energy: {self.energy}")
        else:
            print(f"{self.name} is too tired to play.")
    
    def __str__(self):
        return f"{self.name} is a {self.age}-year-old {self.breed}"

# Usage
my_dog = Dog("Buddy", "Golden Retriever", 3)
print(my_dog)  # "Buddy is a 3-year-old Golden Retriever"
my_dog.bark()  # "Buddy says Woof!"
my_dog.play()  # "Buddy is playing! Energy: 80"
```

This shows constructor, methods, and string representation. Want to learn about inheritance or properties?"""
        
        elif language == 'javascript':
            return """Here's a JavaScript class example:

```javascript
class Car {
    constructor(make, model, year) {
        this.make = make;
        this.model = model;
        this.year = year;
        this.mileage = 0;
    }
    
    start() {
        console.log(`${this.make} ${this.model} is starting...`);
        return 'Engine started!';
    }
    
    drive(miles) {
        this.mileage += miles;
        console.log(`Drove ${miles} miles. Total: ${this.mileage}`);
    }
    
    getInfo() {
        return `${this.year} ${this.make} ${this.model} - ${this.mileage} miles`;
    }
}

// Usage
const myCar = new Car('Toyota', 'Camry', 2022);
console.log(myCar.getInfo()); // "2022 Toyota Camry - 0 miles"
myCar.start();                // "Toyota Camry is starting..."
myCar.drive(150);             // "Drove 150 miles. Total: 150"
```

This shows ES6 class syntax with constructor and methods. Need help with inheritance or static methods?"""
        
        else:
            return "I can help you create classes! Which programming language are you working with? I can show examples in Python, JavaScript, Java, C++, and more. What kind of class are you trying to build?"
    
    def generate_hello_world(self, language):
        """Generate Hello World examples"""
        examples = {
            'python': '''```python
print("Hello, World!")

# Or with a function
def greet():
    return "Hello, World!"

print(greet())
```''',
            'javascript': '''```javascript
console.log("Hello, World!");

// Or with a function
function greet() {
    return "Hello, World!";
}

console.log(greet());

// Or as an arrow function
const greet = () => "Hello, World!";
console.log(greet());
```''',
            'java': '''```java
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}
```''',
            'c++': '''```cpp
#include <iostream>
using namespace std;

int main() {
    cout << "Hello, World!" << endl;
    return 0;
}
```''',
            'html': '''```html
<!DOCTYPE html>
<html>
<head>
    <title>Hello World</title>
</head>
<body>
    <h1>Hello, World!</h1>
</body>
</html>
```'''
        }
        
        if language and language in examples:
            return f"Here's Hello World in {language.title()}:\n\n{examples[language]}\n\nThis is the classic first program! Want to see it in other languages or learn what comes next?"
        else:
            return """Here's Hello World in several popular languages:

**Python:**
```python
print("Hello, World!")
```

**JavaScript:**
```javascript
console.log("Hello, World!");
```

**Java:**
```java
public class HelloWorld {
    public static void main(String[] args) {
        System.out.println("Hello, World!");
    }
}
```

Which language interests you most? I can provide more detailed examples and explain what each part does!"""
    
    def generate_general_coding_help(self, language, message, keywords):
        """Generate general coding help"""
        help_topics = [
            "I'd love to help you with coding! Here are some things I can assist with:",
            "",
            "🔧 **Code Examples**: Functions, loops, classes, data structures",
            "🐛 **Debugging Tips**: Common errors and how to fix them", 
            "📚 **Best Practices**: Clean code, naming conventions, comments",
            "🎯 **Specific Problems**: Algorithm help, logic assistance",
            "💡 **Learning Path**: What to learn next in your coding journey",
            "",
            "What specific coding challenge are you working on? I can provide:",
            "• Step-by-step explanations",
            "• Working code examples", 
            "• Alternative approaches",
            "• Debugging strategies",
            "",
            "Just describe what you're trying to build or the problem you're solving!"
        ]
        
        return "\n".join(help_topics)
    
    def store_learned_knowledge(self, topic, content, confidence, source):
        """Store newly learned knowledge in the knowledge base"""
        topic_lower = topic.lower()
        
        if topic_lower not in self.knowledge_base["topic_knowledge"]:
            self.knowledge_base["topic_knowledge"][topic_lower] = {
                "mentions": 1,
                "contexts": [],
                "facts": [content],
                "confidence": confidence,
                "source": source
            }
        else:
            # Add fact if not already present
            topic_data = self.knowledge_base["topic_knowledge"][topic_lower]
            if content not in topic_data.get("facts", []):
                topic_data["facts"].append(content)
                topic_data["mentions"] = topic_data.get("mentions", 0) + 1
        
        # Save knowledge
        self.save_knowledge()
    
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