import re
from typing import List, Set
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)


class TextProcessor:
    def __init__(self):
        """Initialize text processor with stop words"""
        self.stop_words = set(stopwords.words('english'))

        # Add additional common words to filter
        additional_stops = {
            # Twitter specific
            'rt', 'via', 'http', 'https', 'amp', 'dm', 'cc', 'mt', 'htt',

            # Common verbs
            'get', 'go', 'see', 'know', 'want', 'make', 'got', 'take',
            'come', 'came', 'went', 'going', 'getting', 'making', 'taking',
            'coming', 'seen', 'came', 'give', 'gave', 'giving', 'put',
            'tell', 'told', 'telling', 'let', 'use', 'used', 'using',

            # Common adjectives/adverbs
            'like', 'just', 'new', 'back', 'still', 'even', 'also',
            'really', 'very', 'too', 'well', 'good', 'great', 'best',
            'better', 'right', 'left', 'high', 'low', 'big', 'little',
            'old', 'young', 'long', 'short', 'early', 'late',

            # Common nouns
            'time', 'year', 'day', 'week', 'month', 'today', 'tonight',
            'yesterday', 'tomorrow', 'people', 'thing', 'things', 'way',
            'man', 'woman', 'person', 'lot', 'lots', 'bit', 'something',

            # Pronouns and determiners
            'one', 'two', 'three', 'four', 'five', 'someone', 'anyone',
            'everyone', 'nobody', 'somebody', 'everybody', 'anything',
            'everything', 'nothing', 'us', 'them', 'these', 'those',

            # Common words
            'said', 'say', 'says', 'saying', 'will', 'can', 'could',
            'would', 'should', 'must', 'may', 'might', 'much', 'many',
            'made', 'first', 'last', 'need', 'look', 'looking', 'looks',
            'looked', 'think', 'thought', 'thinking', 'feel', 'felt',
            'feeling', 'believe', 'believe', 'yes', 'yeah', 'yep', 'nope',
            'ok', 'okay', 'sure', 'maybe', 'perhaps', 'probably',

            # Questions words (usually not meaningful)
            'who', 'what', 'when', 'where', 'why', 'how', 'which',

            # Articles and conjunctions (redundant but explicit)
            'the', 'a', 'an', 'and', 'or', 'but', 'if', 'then', 'than',
            'as', 'at', 'by', 'for', 'from', 'in', 'into', 'of', 'on',
            'to', 'with', 'without', 'about', 'after', 'before', 'during',

            # Numbers as words
            'zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
            'eight', 'nine', 'ten', 'hundred', 'thousand', 'million', 'billion',

            # Misc common
            'ever', 'never', 'always', 'often', 'sometimes', 'usually',
            'here', 'there', 'everywhere', 'anywhere', 'somewhere', 'nowhere',
            'next', 'previous', 'another', 'other', 'others', 'same', 'different'
        }
        self.stop_words.update(additional_stops)

    def clean_text(self, text: str) -> str:
        """Clean tweet text"""
        if not text:
            return ""

        # Remove URLs
        text = re.sub(r'http\S+|www\S+|https\S+', '', text, flags=re.MULTILINE)

        # Remove mentions
        text = re.sub(r'@\w+', '', text)

        # Remove hashtags (keep the word, remove #)
        text = re.sub(r'#', '', text)

        # Remove special characters but keep alphanumeric and spaces
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)

        # Remove extra whitespace
        text = ' '.join(text.split())

        return text.strip()

    def extract_keywords(self, text: str, min_length: int = 4) -> List[str]:
        """Extract meaningful keywords from text"""
        cleaned_text = self.clean_text(text)

        if not cleaned_text:
            return []

        # Tokenize and convert to lowercase
        try:
            tokens = word_tokenize(cleaned_text.lower())
        except:
            # Fallback to simple split if tokenization fails
            tokens = cleaned_text.lower().split()

        # Filter stop words and short words - be more aggressive
        keywords = [
            word for word in tokens
            if word.lower() not in self.stop_words  # Ensure lowercase comparison
            and len(word) >= min_length  # Increased to 4 chars minimum
            and word.isalpha()  # Only alphabetic characters
            and not word.isdigit()  # No pure numbers
        ]

        return keywords

    def extract_hashtags(self, text: str) -> List[str]:
        """Extract hashtags from text"""
        if not text:
            return []
        return re.findall(r'#(\w+)', text)

    def extract_mentions(self, text: str) -> List[str]:
        """Extract user mentions from text"""
        if not text:
            return []
        return re.findall(r'@(\w+)', text)

    def get_word_frequency(self, keywords: List[str]) -> dict:
        """Get frequency count of words"""
        freq = {}
        for word in keywords:
            freq[word] = freq.get(word, 0) + 1
        return freq

    def is_relevant_keyword(self, word: str, min_length: int = 3) -> bool:
        """Check if a word is a relevant keyword"""
        if not word or len(word) < min_length:
            return False
        if word.lower() in self.stop_words:
            return False
        if not word.isalpha():
            return False
        return True

    def extract_financial_terms(self, text: str) -> List[str]:
        """Extract financial and market-related terms"""
        financial_keywords = {
            # Markets
            'stock', 'stocks', 'market', 'markets', 'trading', 'trader',
            'nasdaq', 'dow', 'sp500', 's&p', 'bull', 'bear', 'rally',
            'crash', 'correction', 'volatility', 'index', 'indices',

            # Crypto
            'bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'cryptocurrency',
            'blockchain', 'defi', 'nft', 'altcoin', 'token',

            # Commodities
            'gold', 'silver', 'oil', 'crude', 'commodity', 'commodities',
            'wti', 'brent', 'barrel',

            # Economic indicators
            'inflation', 'deflation', 'gdp', 'unemployment', 'jobs',
            'employment', 'cpi', 'ppi', 'recession', 'expansion',
            'interest', 'rates', 'yield', 'bonds', 'treasury',

            # Fed/Policy
            'fed', 'federal', 'reserve', 'fomc', 'powell', 'monetary',
            'policy', 'rate', 'hike', 'cut', 'taper', 'qe', 'quantitative',

            # General finance
            'price', 'prices', 'dollar', 'euro', 'currency', 'forex',
            'investment', 'investing', 'investor', 'portfolio', 'fund',
            'capital', 'profit', 'loss', 'revenue', 'earnings'
        }

        text_lower = text.lower()
        found_terms = []

        for term in financial_keywords:
            if re.search(r'\b' + re.escape(term) + r'\b', text_lower):
                found_terms.append(term)

        return found_terms

    def categorize_text(self, text: str, hashtags: List[str] = None) -> str:
        """Categorize text based on content"""
        text_lower = text.lower()
        hashtags_lower = [h.lower() for h in (hashtags or [])]

        # Trump-related
        trump_keywords = ['trump', 'donald', 'potus', 'maga', 'president trump']
        if any(keyword in text_lower for keyword in trump_keywords):
            return 'trump'

        # FOMC/Fed related
        fed_keywords = ['fomc', 'federal reserve', 'fed', 'powell', 'interest rate', 'monetary policy']
        if any(keyword in text_lower for keyword in fed_keywords):
            return 'fomc'

        # Market/Finance related
        market_keywords = ['stock', 'market', 'trading', 'nasdaq', 'dow', 'sp500']
        if any(keyword in text_lower for keyword in market_keywords):
            return 'markets'

        # Crypto related
        crypto_keywords = ['bitcoin', 'crypto', 'ethereum', 'blockchain', 'btc', 'eth']
        if any(keyword in text_lower for keyword in crypto_keywords):
            return 'crypto'

        # Commodities related
        commodity_keywords = ['gold', 'silver', 'oil', 'crude', 'commodity']
        if any(keyword in text_lower for keyword in commodity_keywords):
            return 'commodities'

        # USA news/politics
        usa_keywords = ['usa', 'america', 'american', 'congress', 'senate', 'washington']
        if any(keyword in text_lower for keyword in usa_keywords):
            return 'usa_news'

        return 'general'
