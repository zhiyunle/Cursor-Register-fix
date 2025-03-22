import time
import imaplib
import email
from email.policy import default
from datetime import datetime
import re

from ._email_server import EmailServer

class Imap(EmailServer):

    def __init__(self, imap_server, imap_port, username, password, email_to = None):
        self.mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        self.mail.login(username, password)

        self.email_to = email_to
        
        self.mail.select('inbox')
        _, data = self.mail.uid("SEARCH", None, 'ALL')
        email_ids = data[0].split()
        self.latest_id = email_ids[-1] if len(email_ids) != 0 else None

    def fetch_emails_since(self, since_timestamp):

        # Get the latest email by id
        self.mail.select('inbox')
        search_criteria = f'UID {int(self.latest_id) + 1}:*' if self.latest_id else 'ALL'
        _, data = self.mail.uid("SEARCH", None, search_criteria)
        email_ids = data[0].split()
        if len(email_ids) == 0:
            return None
        self.latest_id = email_ids[-1]
        
        # Fetch the email message by ID
        _, data = self.mail.uid('FETCH', self.latest_id, '(RFC822)')
        raw_email = data[0][1]
        msg = email.message_from_bytes(raw_email, policy=default)

        # Extract common headers
        from_header = msg.get('From')
        to_header = msg.get('To')
        subject_header = msg.get('Subject')
        date_header = msg.get('Date')

        # Check if the email is intended for the expected recipient
        # For Gmail addresses, compare only the part before "+" in the email address
        if self.email_to is not None:
            expected_base = self.email_to.split('@')[0].split('+')[0]
            expected_domain = self.email_to.split('@')[1]
            
            # Extract the actual recipient address
            if to_header:
                actual_email = to_header
                # Handle case where to_header might be in format "Name <email@example.com>"
                email_match = re.search(r'<([^>]+)>', to_header)
                if email_match:
                    actual_email = email_match.group(1)
                
                # Extract base and domain from actual email
                if '@' in actual_email:
                    actual_base = actual_email.split('@')[0].split('+')[0]
                    actual_domain = actual_email.split('@')[1]
                    
                    # Compare base part (before "+") and domain separately
                    if expected_base != actual_base or expected_domain != actual_domain:
                        return None
            else:
                return None

        email_datetime = datetime.strptime(date_header.replace(' (UTC)', ''), '%a, %d %b %Y %H:%M:%S %z').timestamp()
        if email_datetime < since_timestamp:
            return None

        text_part = msg.get_body(preferencelist=('plain',))
        content = text_part.get_content() if text_part else msg.get_content()

        return {
            "from": from_header,
            "to": to_header,
            "date": date_header,
            "subject": subject_header,
            "content": content
        }
    
    def wait_for_new_message(self, delay=5, timeout=60):
        start_time = time.time()

        while time.time() - start_time <= timeout:
            try:
                email = self.fetch_emails_since(start_time)
                if email is not None:
                    return email
            except:
                pass
            time.sleep(delay)

        return None
