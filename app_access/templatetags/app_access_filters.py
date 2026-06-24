from django import template
from datetime import datetime

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Template filter to get an item from a dictionary by key
    """
    # Handle case where dictionary is None or not a dictionary
    if dictionary is None or not hasattr(dictionary, 'get'):
        return ''
    
    # Convert key to string if it's not already
    str_key = str(key)
    
    # Try to get the item with the string key
    return dictionary.get(str_key, '') 

@register.filter
def date_in_range(date, date_range):
    """
    Filter to check if a date is within a given range
    Usage: {{ date|date_in_range:"start_date,end_date" }}
    Both dates should be in format: YYYY-MM-DD
    """
    if not date:
        return False
    
    try:
        start_date_str, end_date_str = date_range.split(',')
        
        # Convert the database date to datetime object if it's a string
        if isinstance(date, str):
            date = datetime.strptime(date, '%Y-%m-%d').date()
        
        # If date is a datetime object, get just the date part
        if hasattr(date, 'date'):
            date = date.date()
            
        # Parse the start and end dates
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None
        
        # Check if date is in range
        if start_date and end_date:
            return start_date <= date <= end_date
        elif start_date:
            return start_date <= date
        elif end_date:
            return date <= end_date
        return True
    except (ValueError, AttributeError, TypeError) as e:
        return False 