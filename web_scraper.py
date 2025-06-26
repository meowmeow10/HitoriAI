import trafilatura
import requests
from urllib.parse import urljoin, urlparse
import time
import hashlib
import logging
from datetime import datetime, timedelta
import json
import re
from collections import Counter

class WebKnowledgeScraper:
    """Enhanced web scraper for building Hitori's knowledge base"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.default_sources = [
            'https://en.wikipedia.org/wiki/Artificial_intelligence',
            'https://en.wikipedia.org/wiki/Machine_learning',
            'https://en.wikipedia.org/wiki/Natural_language_processing',
            'https://www.britannica.com/technology/artificial-intelligence',
            'https://plato.stanford.edu/entries/artificial-intelligence/',
        ]
        
    def get_website_text_content(self, url: str) -> str:
        """Extract main text content from a website"""
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded)
                return text if text else ""
            return ""
        except Exception as e:
            logging.error(f"Error scraping {url}: {e}")
            return ""
    
    def extract_knowledge_from_text(self, text: str, source_url: str = None) -> list:
        """Extract structured knowledge from text content"""
        if not text or len(text.strip()) < 50:
            return []
        
        knowledge_items = []
        
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        
        # Extract facts and information
        for sentence in sentences[:50]:  # Limit to first 50 sentences
            if self.is_factual_sentence(sentence):
                topics = self.extract_topics_from_sentence(sentence)
                for topic in topics:
                    knowledge_items.append({
                        'topic': topic,
                        'content': sentence.strip(),
                        'source': source_url or 'web_scraping',
                        'confidence_score': self.calculate_confidence_score(sentence)
                    })
        
        return knowledge_items
    
    def is_factual_sentence(self, sentence: str) -> bool:
        """Determine if a sentence contains factual information"""
        # Skip if too short or too long
        if len(sentence) < 20 or len(sentence) > 300:
            return False
        
        # Skip sentences with first person pronouns
        if re.search(r'\b(I|me|my|we|our)\b', sentence, re.IGNORECASE):
            return False
        
        # Look for factual indicators
        factual_patterns = [
            r'\bis\b.*\b(called|known|defined|considered)\b',
            r'\b(developed|created|invented|discovered)\b.*\bin\b.*\d{4}',
            r'\b(consists of|includes|contains|comprises)\b',
            r'\b(according to|research shows|studies indicate)\b',
            r'\b\d+.*\b(percent|percentage|million|billion|thousand)\b'
        ]
        
        return any(re.search(pattern, sentence, re.IGNORECASE) for pattern in factual_patterns)
    
    def extract_topics_from_sentence(self, sentence: str) -> list:
        """Extract main topics from a sentence"""
        # Simple topic extraction based on capitalized words and key phrases
        topics = []
        
        # Extract capitalized words (potential proper nouns)
        capitalized_words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', sentence)
        
        # Extract common technical terms
        tech_terms = re.findall(r'\b(?:artificial intelligence|machine learning|neural network|algorithm|programming|technology|computer|software|data|system)\b', sentence, re.IGNORECASE)
        
        # Combine and clean topics
        all_topics = capitalized_words + tech_terms
        for topic in all_topics:
            topic = topic.strip().lower()
            if len(topic) > 2 and topic not in ['the', 'and', 'but', 'for']:
                topics.append(topic)
        
        return list(set(topics))[:3]  # Return max 3 topics per sentence
    
    def calculate_confidence_score(self, sentence: str) -> float:
        """Calculate confidence score for extracted knowledge"""
        score = 0.5  # Base score
        
        # Increase confidence for factual indicators
        if re.search(r'\b(research|study|according to|published|peer-reviewed)\b', sentence, re.IGNORECASE):
            score += 0.2
        
        # Increase confidence for specific numbers/dates
        if re.search(r'\b\d{4}\b|\b\d+\.?\d*\s*(percent|%|million|billion)\b', sentence):
            score += 0.1
        
        # Decrease confidence for uncertain language
        if re.search(r'\b(might|maybe|possibly|perhaps|could be)\b', sentence, re.IGNORECASE):
            score -= 0.2
        
        return max(0.1, min(1.0, score))
    
    def scrape_url(self, url: str) -> dict:
        """Scrape a single URL and extract knowledge"""
        try:
            # Get content
            content = self.get_website_text_content(url)
            if not content:
                return {'success': False, 'error': 'No content extracted'}
            
            # Calculate content hash
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            # Extract knowledge
            knowledge_items = self.extract_knowledge_from_text(content, url)
            
            return {
                'success': True,
                'url': url,
                'content_hash': content_hash,
                'knowledge_items': knowledge_items,
                'word_count': len(content.split())
            }
        
        except Exception as e:
            logging.error(f"Error scraping {url}: {e}")
            return {'success': False, 'error': str(e)}
    
    def scrape_multiple_sources(self, urls: list = None, max_sources: int = 10) -> dict:
        """Scrape multiple sources and return aggregated knowledge"""
        if not urls:
            urls = self.default_sources
        
        urls = urls[:max_sources]  # Limit number of sources
        
        results = {
            'total_sources': len(urls),
            'successful_scrapes': 0,
            'total_knowledge_items': 0,
            'knowledge_by_topic': {},
            'errors': []
        }
        
        for url in urls:
            try:
                result = self.scrape_url(url)
                
                if result['success']:
                    results['successful_scrapes'] += 1
                    results['total_knowledge_items'] += len(result['knowledge_items'])
                    
                    # Group knowledge by topic
                    for item in result['knowledge_items']:
                        topic = item['topic']
                        if topic not in results['knowledge_by_topic']:
                            results['knowledge_by_topic'][topic] = []
                        results['knowledge_by_topic'][topic].append(item)
                else:
                    results['errors'].append(f"{url}: {result.get('error', 'Unknown error')}")
                
                # Add delay between requests
                time.sleep(1)
                
            except Exception as e:
                results['errors'].append(f"{url}: {str(e)}")
                logging.error(f"Error processing {url}: {e}")
        
        return results
    
    def get_topic_suggestions(self, user_interests: list = None) -> list:
        """Get URLs for specific topics of interest"""
        topic_urls = {
            'technology': [
                'https://en.wikipedia.org/wiki/Technology',
                'https://en.wikipedia.org/wiki/Computer_science',
                'https://en.wikipedia.org/wiki/Software_engineering'
            ],
            'science': [
                'https://en.wikipedia.org/wiki/Science',
                'https://en.wikipedia.org/wiki/Physics',
                'https://en.wikipedia.org/wiki/Biology'
            ],
            'history': [
                'https://en.wikipedia.org/wiki/History',
                'https://en.wikipedia.org/wiki/World_history'
            ],
            'art': [
                'https://en.wikipedia.org/wiki/Art',
                'https://en.wikipedia.org/wiki/Fine_art'
            ],
            'literature': [
                'https://en.wikipedia.org/wiki/Literature',
                'https://en.wikipedia.org/wiki/Fiction'
            ]
        }
        
        if not user_interests:
            # Return a mix of all topics
            all_urls = []
            for topic_list in topic_urls.values():
                all_urls.extend(topic_list[:2])  # Take 2 from each category
            return all_urls
        
        # Return URLs for specific interests
        urls = []
        for interest in user_interests:
            interest = interest.lower()
            if interest in topic_urls:
                urls.extend(topic_urls[interest])
        
        return urls if urls else self.default_sources