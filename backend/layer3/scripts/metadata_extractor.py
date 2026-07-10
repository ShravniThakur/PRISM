import whois
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("metadata_extractor")

def get_domain_age_days(domain: str) -> int:
    """
    Query the WHOIS record for the given domain and calculate its age in days.
    If the lookup fails or the date is missing, defaults to 365 (neutral age).
    """
    if not domain:
        return 0
        
    try:
        w = whois.whois(domain)
        creation_date = w.creation_date
        
        if not creation_date:
            return 0
            
        # whois can sometimes return a list of dates
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
            
        age = (datetime.now() - creation_date).days
        return max(0, age)
        
    except Exception as e:
        log.warning(f"WHOIS lookup failed for {domain}: {e}. Defaulting to 0 days.")
        return 0

if __name__ == "__main__":
    print(f"google.com age: {get_domain_age_days('google.com')} days")
