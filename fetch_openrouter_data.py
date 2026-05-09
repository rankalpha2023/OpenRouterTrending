#!/usr/bin/env python3
"""
OpenRouter Rankings Data Fetcher
Fetches model rankings and top apps data from OpenRouter and saves as JSON.
"""

import re
import json
import argparse
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional
import sys

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class OpenRouterFetcher:
    """Fetch rankings data from OpenRouter."""
    
    BASE_URL = "https://openrouter.ai"
    RANKINGS_URL = f"{BASE_URL}/rankings"
    
    def __init__(self):
        self.session = requests.Session() if HAS_REQUESTS else None
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def _fetch_page(self) -> str:
        """Fetch the rankings page HTML."""
        if self.session:
            response = self.session.get(self.RANKINGS_URL, timeout=30)
            response.raise_for_status()
            return response.text
        else:
            import subprocess
            result = subprocess.run(['curl', '-s', self.RANKINGS_URL], 
                                   capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"curl failed: {result.stderr}")
            return result.stdout
    
    def _extract_rankmap_section(self, content: str, period: str = 'day') -> Optional[str]:
        """Extract the rankMap section for a specific period (day/week/month)."""
        period_key = f'"{period}"'
        start_pattern = f'rankMap\\":{{\\"{period}\\":'
        
        start_idx = content.find(start_pattern)
        if start_idx < 0:
            start_idx = content.find(f'rankMap\\":{{\\"{period}"')
        
        if start_idx < 0:
            return None
        
        # Find the start of the array
        array_start = content.find('[', start_idx)
        if array_start < 0:
            return None
        
        # Find the end - look for next period or closing braces
        search_start = array_start + 1
        brace_count = 1
        
        # Find the matching closing bracket
        for i, char in enumerate(content[search_start:], search_start):
            if char == '[':
                brace_count += 1
            elif char == ']':
                brace_count -= 1
                if brace_count == 0:
                    return content[array_start+1:i]
        
        return None
    
    def _parse_apps_from_chunk(self, chunk: str) -> List[Dict[str, Any]]:
        """Parse app entries from the rankMap chunk."""
        # Unescape the JSON
        unescaped = chunk.replace('\\"', '"').replace('\\n', ' ')
        
        apps = []
        pos = 0
        
        while True:
            app_start = unescaped.find('"app_id"', pos)
            if app_start < 0:
                break
            
            app_end = unescaped.find('"app_id"', app_start + 10)
            if app_end < 0:
                app_end = len(unescaped)
            
            block = unescaped[app_start:app_end].strip()
            if block.endswith(','):
                block = block[:-1]
            
            if block:
                app = self._parse_app_block(block)
                if app:
                    apps.append(app)
            
            pos = app_end
        
        return apps
    
    def _parse_app_block(self, block: str) -> Optional[Dict[str, Any]]:
        """Parse a single app block."""
        rank_match = re.search(r'"rank":(\d+)', block)
        app_id_match = re.search(r'"app_id":(\d+)', block)
        tokens_match = re.search(r'"total_tokens":"(\d+)"', block)
        requests_match = re.search(r'"total_requests":(\d+)', block)
        title_match = re.search(r'"title":"([^"]*)"', block)
        slug_match = re.search(r'"slug":"([^"]*)"', block)
        desc_match = re.search(r'"description":"([^"]*)"', block)
        origin_match = re.search(r'"origin_url":"([^"]*)"', block)
        cats_match = re.search(r'"categories":\[([^\]]*)\]', block)
        
        if not (rank_match and app_id_match and tokens_match):
            return None
        
        categories = []
        if cats_match:
            categories = re.findall(r'"([^"]+)"', cats_match.group(1))
        
        return {
            'rank': int(rank_match.group(1)),
            'app_id': int(app_id_match.group(1)),
            'total_tokens': int(tokens_match.group(1)),
            'total_requests': int(requests_match.group(1)) if requests_match else 0,
            'app': {
                'title': title_match.group(1) if title_match else None,
                'slug': slug_match.group(1) if slug_match else None,
                'description': desc_match.group(1) if desc_match else None,
                'origin_url': origin_match.group(1) if origin_match else None,
                'categories': categories
            }
        }
    
    def _parse_models_from_chunk(self, chunk: str) -> List[Dict[str, Any]]:
        """Parse model entries from the rankMap chunk."""
        unescaped = chunk.replace('\\"', '"').replace('\\n', ' ')
        
        models = []
        pos = 0
        
        while True:
            # Look for model patterns - could be "id", "model_id", or other identifiers
            # The model data structure is different from apps
            id_start = unescaped.find('"id":"', pos)
            if id_start < 0:
                id_start = unescaped.find('"model_id"', pos)
            
            if id_start < 0:
                break
            
            # Find end of this model block
            next_id = unescaped.find('"id":"', id_start + 6)
            next_model = unescaped.find('"model_id"', id_start + 1)
            
            end_positions = [p for p in [next_id, next_model] if p > 0]
            model_end = min(end_positions) if end_positions else len(unescaped)
            
            block = unescaped[id_start:model_end].strip()
            
            model = self._parse_model_block(block)
            if model:
                models.append(model)
            
            pos = model_end
        
        return models
    
    def _parse_model_block(self, block: str) -> Optional[Dict[str, Any]]:
        """Parse a single model block."""
        # Look for common model fields
        id_match = re.search(r'"id":"([^"]*)"', block)
        name_match = re.search(r'"name":"([^"]*)"', block)
        provider_match = re.search(r'"provider":"([^"]*)"', block)
        tokens_match = re.search(r'"total_tokens":"(\d+)"', block)
        rank_match = re.search(r'"rank":(\d+)', block)
        
        # Try alternative field names
        if not id_match:
            id_match = re.search(r'"model":"([^"]*)"', block)
        
        if not (id_match or name_match):
            return None
        
        return {
            'id': id_match.group(1) if id_match else None,
            'name': name_match.group(1) if name_match else None,
            'provider': provider_match.group(1) if provider_match else None,
            'total_tokens': int(tokens_match.group(1)) if tokens_match else 0,
            'rank': int(rank_match.group(1)) if rank_match else None
        }
    
    def fetch_top_apps(self, period: str = 'day') -> Dict[str, Any]:
        """
        Fetch Top Apps rankings.
        
        Args:
            period: Time period - 'day', 'week', or 'month'
        
        Returns:
            Dictionary with apps data
        """
        content = self._fetch_page()
        chunk = self._extract_rankmap_section(content, period)
        
        if not chunk:
            return {'error': f'Could not find {period} data'}
        
        apps = self._parse_apps_from_chunk(chunk)
        
        # Deduplicate by (app_id, rank)
        seen = set()
        unique_apps = []
        for app in apps:
            key = (app['app_id'], app['rank'])
            if key not in seen:
                seen.add(key)
                unique_apps.append(app)
        
        # Sort by rank
        unique_apps.sort(key=lambda x: x['rank'])
        
        period_labels = {
            'day': 'Day (Today)',
            'week': 'Week',
            'month': 'Month'
        }
        
        return {
            'source': self.RANKINGS_URL,
            'section': 'Top Apps',
            'subsection': period_labels.get(period, period),
            'extracted_at': datetime.now().isoformat(),
            'period': period,
            'description': 'Top AI applications and agents ranked by token usage on OpenRouter',
            'total_apps': len(unique_apps),
            'apps': unique_apps
        }
    
    def fetch_models(self, period: str = 'week') -> Dict[str, Any]:
        """
        Fetch Model Rankings.
        
        Args:
            period: Time period - 'day', 'week', or 'month'
        
        Returns:
            Dictionary with models data
        """
        content = self._fetch_page()
        chunk = self._extract_rankmap_section(content, period)
        
        if not chunk:
            return {'error': f'Could not find {period} data'}
        
        models = self._parse_models_from_chunk(chunk)
        
        # Sort by rank if available
        models.sort(key=lambda x: x.get('rank', 999) if x.get('rank') else 999)
        
        period_labels = {
            'day': 'Day (Today)',
            'week': 'Week',
            'month': 'Month'
        }
        
        return {
            'source': self.RANKINGS_URL,
            'section': 'Model Rankings',
            'subsection': period_labels.get(period, period),
            'extracted_at': datetime.now().isoformat(),
            'period': period,
            'description': 'LLM Model rankings based on usage data from OpenRouter',
            'total_models': len(models),
            'models': models
        }


def save_data(data: Dict[str, Any], output_path: Path) -> None:
    """Save data to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Fetch OpenRouter rankings data')
    parser.add_argument('--output-dir', '-o', type=Path, default=Path('data'),
                       help='Output directory for data files')
    parser.add_argument('--date', '-d', type=str, default=None,
                       help='Date for filename (YYYY-MM-DD), defaults to today')
    parser.add_argument('--section', '-s', choices=['all', 'apps', 'models'], 
                       default='all', help='Section to fetch')
    parser.add_argument('--period', '-p', choices=['day', 'week', 'month'],
                       default='week', help='Time period for rankings')
    
    args = parser.parse_args()
    
    # Determine date for filename
    if args.date:
        file_date = args.date
    else:
        file_date = date.today().isoformat()
    
    fetcher = OpenRouterFetcher()
    
    try:
        # Fetch Top Apps
        if args.section in ['all', 'apps']:
            print("Fetching Top Apps...")
            apps_data = fetcher.fetch_top_apps(args.period)
            if 'error' not in apps_data:
                apps_path = args.output_dir / 'top_apps' / f'{file_date}.json'
                save_data(apps_data, apps_path)
            else:
                print(f"Error fetching apps: {apps_data['error']}")
        
        # Fetch Model Rankings
        if args.section in ['all', 'models']:
            print("Fetching Model Rankings...")
            models_data = fetcher.fetch_models(args.period)
            if 'error' not in models_data:
                models_path = args.output_dir / 'models' / f'{file_date}.json'
                save_data(models_data, models_path)
            else:
                print(f"Error fetching models: {models_data['error']}")
        
        print("Done!")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()