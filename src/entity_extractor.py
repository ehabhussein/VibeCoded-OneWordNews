"""
Entity Recognition using spaCy
Extracts companies, people, locations, organizations, and other entities from news articles
"""
import logging
import spacy
from typing import Dict, List, Any
from collections import Counter
import re


class EntityExtractor:
    def __init__(self):
        """Initialize spaCy entity extractor"""
        self.logger = logging.getLogger(__name__)

        try:
            # Load English language model
            self.logger.info("Loading spaCy English model for entity recognition...")
            self.nlp = spacy.load("en_core_web_sm")
            self.logger.info("spaCy model loaded successfully")
        except Exception as e:
            self.logger.error(f"Error loading spaCy model: {e}")
            self.nlp = None

        # Patterns that indicate an entity is likely an organization/product, not a person
        self.org_indicators = [
            r'\bCoin$', r'\bToken$', r'\bChain$', r'\bExchange$', r'\bWallet$',
            r'\bPlatform$', r'\bProtocol$', r'\bNetwork$', r'\bFinance$',
            r'\bBanking$', r'\bCapital$', r'\bGroup$', r'\bCorp\b', r'\bInc\b',
            r'\bLLC\b', r'\bLtd\b', r'\bCo\b', r'\bCompany$', r'\bSystems?$',
            r'\bTechnolog(?:y|ies)$', r'\bSolutions?$', r'\bServices?$',
            r'\bMedia$', r'\bNews$', r'\bPress$', r'\bTimes$', r'\bPost$',
            r'\bBroadcasting$', r'\bPublishing$', r'\bFoundation$',
            r'\bAssociation$', r'\bInstitute$', r'\bCouncil$', r'\bFederation$',
            r'\bUnion$', r'\bLeague$', r'\bAlliance$', r'\bCoalition$'
        ]

        # Compile patterns for efficiency
        self.org_pattern = re.compile('|'.join(self.org_indicators), re.IGNORECASE)

    def _improve_entity_classification(self, entity_text: str, label: str, doc) -> str:
        """
        Improve entity classification using context and patterns
        Returns the corrected label
        """
        # Check if entity matches organization patterns
        if label == 'PERSON' and self.org_pattern.search(entity_text):
            return 'ORG'

        # Check if entity is all uppercase (likely an acronym/organization)
        if label == 'PERSON' and len(entity_text) > 2 and entity_text.isupper():
            return 'ORG'

        # Check if entity has title case with multiple words (might be company)
        words = entity_text.split()
        if label == 'PERSON' and len(words) >= 2:
            # If it contains corporate keywords in context
            for sent in doc.sents:
                if entity_text in sent.text:
                    sent_lower = sent.text.lower()
                    # Look for corporate context clues
                    if any(clue in sent_lower for clue in [
                        'company', 'corporation', 'inc', 'llc', 'ltd', 'exchange',
                        'platform', 'announced', 'launches', 'ceo of', 'founded',
                        'startup', 'firm', 'venture', 'enterprise', 'organization'
                    ]):
                        return 'ORG'

        # If entity contains no spaces and looks like a brand/product
        if label == 'PERSON' and ' ' not in entity_text and len(entity_text) > 2:
            # Check if it's capitalized strangely (like iPhone, eBay, etc.)
            if entity_text[0].isupper() or entity_text[0].islower():
                # If there's a capital letter in the middle, likely a brand
                if any(c.isupper() for c in entity_text[1:]):
                    return 'ORG'

        return label

    def extract_entities(self, text: str) -> Dict[str, Any]:
        """
        Extract named entities from text

        Returns:
            {
                'persons': ['Elon Musk', 'Joe Biden', ...],
                'organizations': ['Tesla', 'Apple Inc.', ...],
                'locations': ['United States', 'New York', ...],
                'money': ['$1 billion', '$50', ...],
                'dates': ['Monday', 'January 2024', ...],
                'products': ['iPhone', 'Bitcoin', ...],
                'events': ['World War II', 'Super Bowl', ...],
                'all_entities': [
                    {'text': 'Apple Inc.', 'label': 'ORG', 'count': 3},
                    ...
                ]
            }
        """
        if not self.nlp:
            return self._get_empty_result()

        try:
            # Process text with spaCy
            doc = self.nlp(text)

            # Collect entities by type
            entities_by_type = {
                'persons': [],       # PERSON
                'organizations': [], # ORG
                'locations': [],     # GPE (geopolitical entity), LOC
                'money': [],         # MONEY
                'dates': [],         # DATE, TIME
                'products': [],      # PRODUCT
                'events': [],        # EVENT
                'other': []          # Other types
            }

            # Extract entities with improved classification
            for ent in doc.ents:
                entity_text = ent.text.strip()

                # Skip single characters and very short entities
                if len(entity_text) <= 1:
                    continue

                # Improve classification using context
                corrected_label = self._improve_entity_classification(entity_text, ent.label_, doc)

                # Categorize by corrected entity type
                if corrected_label == 'PERSON':
                    entities_by_type['persons'].append(entity_text)
                elif corrected_label == 'ORG':
                    entities_by_type['organizations'].append(entity_text)
                elif corrected_label in ('GPE', 'LOC'):  # Geographic/Location
                    entities_by_type['locations'].append(entity_text)
                elif corrected_label == 'MONEY':
                    entities_by_type['money'].append(entity_text)
                elif corrected_label in ('DATE', 'TIME'):
                    entities_by_type['dates'].append(entity_text)
                elif corrected_label == 'PRODUCT':
                    entities_by_type['products'].append(entity_text)
                elif corrected_label == 'EVENT':
                    entities_by_type['events'].append(entity_text)
                else:
                    entities_by_type['other'].append(entity_text)

            # Count entity frequencies with improved classification
            all_entities_list = []
            for ent in doc.ents:
                if len(ent.text.strip()) > 1:
                    # Apply classification improvement
                    corrected_label = self._improve_entity_classification(ent.text.strip(), ent.label_, doc)
                    all_entities_list.append({
                        'text': ent.text.strip(),
                        'label': corrected_label
                    })

            # Count occurrences of each entity
            entity_counts = Counter([f"{e['text']}|{e['label']}" for e in all_entities_list])

            # Format counted entities
            all_entities = []
            for entity_key, count in entity_counts.items():
                text, label = entity_key.split('|')
                all_entities.append({
                    'text': text,
                    'label': label,
                    'count': count
                })

            # Sort by count (most mentioned first)
            all_entities.sort(key=lambda x: x['count'], reverse=True)

            return {
                'persons': list(set(entities_by_type['persons'])),
                'organizations': list(set(entities_by_type['organizations'])),
                'locations': list(set(entities_by_type['locations'])),
                'money': list(set(entities_by_type['money'])),
                'dates': list(set(entities_by_type['dates'])),
                'products': list(set(entities_by_type['products'])),
                'events': list(set(entities_by_type['events'])),
                'all_entities': all_entities
            }

        except Exception as e:
            self.logger.error(f"Error extracting entities: {e}")
            return self._get_empty_result()

    def get_top_entities(self, entities_data: Dict[str, Any], top_n: int = 10) -> List[Dict[str, Any]]:
        """Get top N entities from extracted data"""
        all_entities = entities_data.get('all_entities', [])
        return all_entities[:top_n]

    def get_entities_by_type(self, entities_data: Dict[str, Any], entity_type: str) -> List[str]:
        """Get entities of a specific type"""
        return entities_data.get(entity_type, [])

    def _get_empty_result(self) -> Dict[str, Any]:
        """Return empty result structure"""
        return {
            'persons': [],
            'organizations': [],
            'locations': [],
            'money': [],
            'dates': [],
            'products': [],
            'events': [],
            'all_entities': []
        }
