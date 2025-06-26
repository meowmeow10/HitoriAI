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
        # Initialize database connection
        self.database_url = database_url or os.environ.get('DATABASE_URL')
        self.engine = None
        self.Session = None
        self.db_session = None
        self.web_scraper = None
        
        if self.database_url:
            try:
                self.engine = create_engine(
                    self.database_url,
                    pool_recycle=300,
                    pool_pre_ping=True,
                    connect_args={"sslmode": "prefer"}
                )
                Base.metadata.create_all(self.engine)
                self.Session = sessionmaker(bind=self.engine)
                self.db_session = self.Session()
                self.web_scraper = WebKnowledgeScraper(self.db_session)
                logging.info("Database connection established")
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
        
        # First look for special patterns (names with special characters, etc.)
        special_keywords = re.findall(r'\b[A-Za-z]+[!-][A-Za-z]*\b|\b[A-Z][a-z]*-[A-Z][a-z]*\b', message)
        
        # Extract words and filter out stop words
        words = re.findall(r'\b[a-zA-Z]+\b', message.lower())
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Add special keywords back
        keywords.extend([kw.lower() for kw in special_keywords])
        
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
        if random.choice([True, False]):
            starter = random.choice(self.response_patterns["question_starters"])
            response_parts.append(f"{starter} {main_keyword},")
        
        # Add topic information
        if "facts" in topic_info:
            fact = random.choice(topic_info["facts"])
            response_parts.append(fact)
        
        # Add continuation question
        if random.choice([True, False]):
            continuation = random.choice(self.response_patterns["continuation_phrases"])
            response_parts.append(continuation)
        
        return " ".join(response_parts)
    
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
    
    def add_learned_pattern(self, user_message, ai_response):
        """Add new learned patterns"""
        # Simple pattern learning - if user says something multiple times, learn it
        pattern_key = user_message[:20]  # Use first 20 chars as pattern key
        
        if pattern_key not in self.knowledge_base["learned_responses"]:
            self.knowledge_base["learned_responses"][pattern_key] = []
        
        # Don't duplicate responses
        if ai_response not in self.knowledge_base["learned_responses"][pattern_key]:
            self.knowledge_base["learned_responses"][pattern_key].append(ai_response)
    
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
        """Generate response using database knowledge or file-based knowledge"""
        # Try database first
        db_knowledge = self.get_knowledge_from_database(keywords)
        
        # If no database knowledge, check file-based knowledge
        if not db_knowledge:
            db_knowledge = self.get_knowledge_from_memory(keywords)
        
        if db_knowledge:
            # Use knowledge to enhance response
            main_keyword = keywords[0] if keywords else "that topic"
            
            # Select best knowledge item
            best_knowledge = max(db_knowledge, key=lambda x: x.get('confidence', 0.5))
            
            responses = [
                f"I know about {main_keyword}! {best_knowledge['content']} What would you like to know more about?",
                f"That's interesting about {main_keyword}. From what I've learned: {best_knowledge['content']} How does that relate to your question?",
                f"I've been learning about {main_keyword}. {best_knowledge['content']} What's your experience with this?",
                f"Based on my knowledge of {main_keyword}: {best_knowledge['content']} What aspect interests you most?"
            ]
            
            return random.choice(responses)
        
        # Fallback to original response generation
        return self.generate_response(message, keywords)
    
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