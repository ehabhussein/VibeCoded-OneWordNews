"""
Forex Factory Calendar Scraper
Fetches economic calendar events from ForexFactory
"""
import logging
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
import random


class ForexEvent:
    def __init__(self):
        self.id = None
        self.date = None
        self.time = None
        self.currency = None
        self.impact = None
        self.event_name = None
        self.actual = None
        self.forecast = None
        self.previous = None

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'time': self.time,
            'currency': self.currency,
            'impact': self.impact,
            'event_name': self.event_name,
            'actual': self.actual,
            'forecast': self.forecast,
            'previous': self.previous
        }


class ForexFactoryScraper:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.base_url = "https://www.forexfactory.com"

        # Headers to mimic a real browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

        # Cookies that ForexFactory expects
        self.cookies = {
            'ffdstonoff': '0',
            'fftimezone': '0',
            'ffverifytimes': '1'
        }

    async def get_week_data_async(self, week: str = None) -> Dict:
        """Get calendar data for a specific week"""
        try:
            url = f"{self.base_url}/calendar"
            if week:
                url += f"?week={week}"

            self.logger.warning(f"Fetching Forex Factory calendar from: {url}")

            # Add delay to avoid rate limiting
            await asyncio.sleep(random.uniform(0.5, 1.5))

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=self.headers, cookies=self.cookies) as response:
                    self.logger.warning(f"Forex Factory response status: {response.status}")

                    if response.status == 403:
                        self.logger.warning("ForexFactory blocked (403). Returning empty calendar.")
                        return {
                            'week': week or datetime.now().strftime("%b %d, %Y"),
                            'last_updated': datetime.now().isoformat(),
                            'events': []
                        }

                    if response.status != 200:
                        raise Exception(f"Failed to fetch calendar data. Status: {response.status}")

                    html = await response.text()
                    self.logger.warning(f"Received HTML response of length: {len(html)}")
                    return self._parse_calendar_data(html, week)

        except asyncio.TimeoutError:
            self.logger.error("Request timeout fetching calendar data")
            raise Exception("Request timeout fetching calendar data")
        except Exception as e:
            self.logger.error(f"Failed to fetch calendar data: {e}")
            raise

    def get_week_data(self, week: str = None) -> Dict:
        """Synchronous wrapper for get_week_data_async"""
        try:
            # Always create a new event loop for thread-safe execution
            return asyncio.run(self.get_week_data_async(week))
        except Exception as e:
            self.logger.error(f"Error in get_week_data: {e}")
            return {
                'week': week or datetime.now().strftime("%b %d, %Y"),
                'last_updated': datetime.now().isoformat(),
                'events': []
            }

    def get_today_data(self) -> Dict:
        """Get calendar data for today"""
        return self.get_week_data()

    def get_week_data_by_date(self, date: datetime) -> Dict:
        """Get calendar data for a specific date"""
        week_format = self._get_week_format(date)
        return self.get_week_data(week_format)

    def _get_week_format(self, date: datetime) -> str:
        """Convert date to ForexFactory week format (e.g., 'aug24.2025')"""
        # Find the Sunday of the week containing the date
        days_until_sunday = date.weekday() + 1  # Monday=0, Sunday=6
        if days_until_sunday == 7:
            days_until_sunday = 0
        sunday = date - timedelta(days=days_until_sunday)

        # Format as "mmmdd.yyyy" (e.g., "aug24.2025")
        month_abbr = sunday.strftime("%b").lower()
        day = str(sunday.day)
        year = str(sunday.year)

        return f"{month_abbr}{day}.{year}"

    def _parse_calendar_data(self, html: str, week: str = None) -> Dict:
        """Parse HTML to extract calendar events"""
        calendar_week = {
            'week': week or datetime.now().strftime("%b %d, %Y"),
            'last_updated': datetime.now().isoformat(),
            'events': []
        }

        soup = BeautifulSoup(html, 'html.parser')

        # Find the calendar table
        calendar_table = soup.find('table', class_='calendar__table')
        if not calendar_table:
            self.logger.warning("Calendar table not found in HTML")
            return calendar_week

        self.logger.warning("Found calendar table, parsing rows...")

        # Find all rows - try different selectors
        rows = calendar_table.find_all('tr', class_='calendar__row')
        if not rows:
            self.logger.warning("No rows found with calendar__row class, trying all tr tags")
            rows = calendar_table.find_all('tr')

        if not rows:
            self.logger.warning("No rows found in calendar table at all")
            return calendar_week

        self.logger.warning(f"Found {len(rows)} rows in calendar table")

        current_date = datetime.now()  # Set current date as default
        parsed_events = 0
        dates_found = 0

        for row in rows:
            # Check if it's a day breaker row
            day_breaker = row.find('td', class_='calendar__date')
            if not day_breaker:
                day_breaker = row.find('td', {'class': lambda x: x and 'date' in str(x).lower()})

            if day_breaker:
                date_span = day_breaker.find('span', class_='date')
                if not date_span:
                    date_span = day_breaker.find('span')

                if date_span:
                    date_text = date_span.get_text(strip=True)
                    self.logger.warning(f"Found date text: '{date_text}'")
                    parsed_date = self._try_parse_date(date_text)
                    if parsed_date:
                        current_date = parsed_date
                        dates_found += 1
                        self.logger.warning(f"Parsed date: {current_date}")
                continue

            # Always try to parse the row (we have a default date)

            # Parse event row
            event_data = self._parse_event_row(row, current_date)
            if event_data:
                calendar_week['events'].append(event_data.to_dict())
                parsed_events += 1

        self.logger.warning(f"Found {dates_found} dates in calendar")
        self.logger.warning(f"Parsed {parsed_events} events from {len(rows)} rows")
        self.logger.warning(f"Total events in calendar: {len(calendar_week['events'])}")
        return calendar_week

    def _parse_event_row(self, row, date: datetime) -> Optional[ForexEvent]:
        """Parse a single event row"""
        try:
            event = ForexEvent()
            event.date = date
            event.id = f"{date.strftime('%Y%m%d')}_{random.randint(1000, 9999)}"

            # Time - try multiple ways to find it
            time_cell = row.find('td', class_='calendar__time')
            if not time_cell:
                time_cell = row.find('td', {'class': lambda x: x and 'time' in str(x).lower()})
            if time_cell:
                event.time = time_cell.get_text(strip=True)

            # Currency
            currency_cell = row.find('td', class_='calendar__currency')
            if not currency_cell:
                currency_cell = row.find('td', {'class': lambda x: x and 'currency' in str(x).lower()})
            if currency_cell:
                event.currency = currency_cell.get_text(strip=True)

            # Impact - look for impact indicators
            impact_cell = row.find('td', class_='calendar__impact')
            if not impact_cell:
                impact_cell = row.find('td', {'class': lambda x: x and 'impact' in str(x).lower()})

            if impact_cell:
                # Check for impact icon
                impact_span = impact_cell.find('span')
                if impact_span:
                    impact_class = impact_span.get('class', [])
                    if isinstance(impact_class, list):
                        impact_class_str = ' '.join(impact_class)
                    else:
                        impact_class_str = str(impact_class)

                    if 'high' in impact_class_str.lower() or 'red' in impact_class_str.lower():
                        event.impact = 'High'
                    elif 'medium' in impact_class_str.lower() or 'orange' in impact_class_str.lower():
                        event.impact = 'Medium'
                    elif 'low' in impact_class_str.lower() or 'yellow' in impact_class_str.lower():
                        event.impact = 'Low'
                    else:
                        event.impact = 'None'

            # Event Name
            event_cell = row.find('td', class_='calendar__event')
            if not event_cell:
                event_cell = row.find('td', {'class': lambda x: x and 'event' in str(x).lower()})

            if event_cell:
                # Try to find event title
                event_span = event_cell.find('span', class_='calendar__event-title')
                if not event_span:
                    event_span = event_cell.find('span')
                if event_span:
                    event.event_name = event_span.get_text(strip=True)
                elif event_cell:
                    event.event_name = event_cell.get_text(strip=True)

            # Actual
            actual_cell = row.find('td', class_='calendar__actual')
            if actual_cell:
                event.actual = actual_cell.get_text(strip=True)

            # Forecast
            forecast_cell = row.find('td', class_='calendar__forecast')
            if forecast_cell:
                event.forecast = forecast_cell.get_text(strip=True)

            # Previous
            previous_cell = row.find('td', class_='calendar__previous')
            if previous_cell:
                event.previous = previous_cell.get_text(strip=True)

            # Only return if we have at least an event name and it's not empty
            if event.event_name and len(event.event_name.strip()) > 0:
                return event

        except Exception as e:
            self.logger.error(f"Error parsing event row: {e}")

        return None

    def _try_parse_date(self, date_text: str) -> Optional[datetime]:
        """Try to parse date string into datetime object"""
        try:
            # Handle format like "SunOct 5" or "MonOct 6"
            # Remove the day of week (first 3 chars)
            if len(date_text) > 3:
                # Remove day of week prefix (e.g., "Sun", "Mon", etc.)
                date_without_dow = date_text[3:]  # Remove first 3 characters

                # Try to parse month and day
                formats = [
                    "%b%d",      # Oct5
                    "%b %d",     # Oct 5
                    "%B%d",      # October5
                    "%B %d",     # October 5
                ]

                for fmt in formats:
                    try:
                        parsed = datetime.strptime(date_without_dow, fmt)
                        # Add current year
                        result = parsed.replace(year=datetime.now().year)
                        self.logger.warning(f"Successfully parsed '{date_text}' to {result}")
                        return result
                    except ValueError:
                        continue

            # Fallback: try original parsing
            parts = date_text.split()
            if len(parts) >= 2:
                month_day = ' '.join(parts[-2:])
                formats = ["%b %d", "%B %d"]
                for fmt in formats:
                    try:
                        parsed = datetime.strptime(month_day, fmt)
                        return parsed.replace(year=datetime.now().year)
                    except ValueError:
                        continue

        except Exception as e:
            self.logger.error(f"Error parsing date '{date_text}': {e}")

        return None
