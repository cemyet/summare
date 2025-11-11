"""
TellusTalk eBox API Service for Digital Signatures
Sends PDFs for digital signing using TellusTalk's eBox API v1
"""
import os
import base64
import requests
import secrets
import string
import time
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# TellusTalk API Configuration
TELLUSTALK_BASE_URL = "https://k8api.tellustalk.com"
TELLUSTALK_EBOX_ENDPOINT = f"{TELLUSTALK_BASE_URL}/api/ebox/v1"

def get_tellustalk_credentials() -> tuple[str, str]:
    """
    Get TellusTalk API credentials from environment variables
    
    Returns:
        Tuple of (username, password)
    """
    username = os.getenv("TELLUSTALK_USERNAME")
    password = os.getenv("TELLUSTALK_PASSWORD")
    
    if not username or not password:
        raise ValueError(
            "TellusTalk credentials not configured. "
            "Please set TELLUSTALK_USERNAME and TELLUSTALK_PASSWORD environment variables."
        )
    
    return username, password


def create_basic_auth_header(username: str, password: str) -> str:
    """
    Create Basic Authentication header
    
    Args:
        username: TellusTalk username
        password: TellusTalk password
        
    Returns:
        Authorization header value
    """
    credentials = f"{username}:{password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


def generate_object_id(length: int = 12) -> str:
    """
    Generate a unique object ID (member_id or attachment_id)
    Must be minimum 8 characters, alphanumeric A-Za-z0-9
    
    Args:
        length: Length of ID to generate (default 12)
        
    Returns:
        Unique alphanumeric string
    """
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(max(length, 8)))


def format_personnummer(personnummer: str) -> str:
    """
    Format personnummer to YYYYMMDD-XXXX format if needed
    
    Args:
        personnummer: Personnummer in any format
        
    Returns:
        Formatted personnummer (YYYYMMDD-XXXX)
    """
    # Remove any existing dashes and spaces
    cleaned = personnummer.replace("-", "").replace(" ", "").strip()
    
    # If it's 10 digits (no century), add century
    if len(cleaned) == 10:
        # Assume 1900s for dates > 50, 2000s for dates <= 50
        year_prefix = cleaned[:2]
        if int(year_prefix) > 50:
            cleaned = "19" + cleaned
        else:
            cleaned = "20" + cleaned
    
    # Format as YYYYMMDD-XXXX
    if len(cleaned) == 12:
        return f"{cleaned[:8]}-{cleaned[8:12]}"
    
    return personnummer


def send_pdf_for_signing(
    pdf_bytes: bytes,
    signers: List[Dict[str, Any]],
    job_name: str,
    success_redirect_url: Optional[str] = None,
    fail_redirect_url: Optional[str] = None,
    report_to_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send PDF document to TellusTalk for digital signing using eBox API v1
    
    Args:
        pdf_bytes: PDF file as bytes
        signers: List of signer dictionaries with:
            - name: Full name of signer
            - email: Email address for signing invitation
            - personal_id: Personnummer (required for BankID)
            - signature_order: Order in which to sign (1, 2, 3, etc.)
        job_name: Name of the signing job
        success_redirect_url: URL to redirect after successful signing (optional)
        fail_redirect_url: URL to redirect after failed signing (optional)
        report_to_url: Callback URL for job status updates (optional)
        
    Returns:
        Dictionary with:
            - success: Boolean indicating if request was successful
            - job_uuid: Unique identifier for the signing job
            - job_name: Name of the job
            - members: List of members with their URLs
            - message: Success or error message
            
    Raises:
        ValueError: If credentials are missing or request is invalid
        requests.RequestException: If API request fails
    """
    try:
        # Get credentials
        username, password = get_tellustalk_credentials()
        
        # Encode PDF to base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        # Generate unique IDs
        attachment_id = generate_object_id()
        
        # Build config object
        config = {
            "job_name": job_name,
            "acl": ["view"]
        }
        
        # Configure webhook callbacks for signing status updates
        # Only configure job_completed to avoid delays - we don't need immediate feedback
        # The job_started and signature_completed events can cause TellusTalk to validate
        # the webhook URL synchronously, causing delays in the API response
        if report_to_url:
            config["events"] = {
                # Only configure job_completed event to minimize API response delay
                # TellusTalk may validate webhook URLs synchronously, causing slow responses
                "job_completed": {
                    "report_to": [{
                        "address": report_to_url,
                        "headers": {
                            "Content-Type": "application/json"
                        }
                    }],
                    "include_signed_files": True  # Include final signed PDF when job completes
                }
            }
        
        # Build members array
        members = []
        for idx, signer in enumerate(signers):
            member_id = generate_object_id()
            personal_id = signer.get("personal_id", "")
            email = signer.get("email", "")
            name = signer.get("name", "")
            signature_order = signer.get("signature_order", idx + 1)
            
            if not personal_id:
                raise ValueError(f"personal_id (personnummer) is required for signer: {name}")
            
            if not email:
                raise ValueError(f"email is required for signer: {name}")
            
            # Format personnummer
            formatted_personal_id = format_personnummer(personal_id)
            
            # Build member object according to API spec
            member = {
                "member_id": member_id,
                "acl": ["view"],
                "authorizations": ["view"],
                "name": name,
                "review": False,
                "edit_file": False,
                "addresses": [
                    {
                        "address": f"email:{email}"
                    }
                ],
                "signature_options": {
                    "signature_methods": [
                        {
                            "type": "bankid",
                            "personal_id": formatted_personal_id,
                            "hide_personal_id": False
                        }
                    ],
                    "signature_order": signature_order
                }
            }
            
            members.append(member)
        
        # Build attachment object
        attachment = {
            "attachment_id": attachment_id,
            "acl": ["view"],
            "name": "arsredovisning.pdf",
            "content_transfer_encoding": "base64",
            "content_type": "application/pdf",
            "payload": pdf_base64,
            "attachment_purpose": "SIGNATORY"
        }
        
        # Build complete request payload
        payload = {
            "config": config,
            "members": members,
            "attachments": [attachment]
        }
        
        # Prepare request headers
        headers = {
            "Authorization": create_basic_auth_header(username, password),
            "Content-Type": "application/json"
        }
        
        # Make API request with retry logic and increased timeout
        logger.info(f"Sending PDF to TellusTalk eBox API: {job_name}")
        logger.info(f"Number of signers: {len(signers)}")
        
        # Retry configuration
        max_retries = 3
        retry_delays = [2, 5, 10]  # Exponential backoff delays in seconds
        connect_timeout = 10  # Connection timeout (reduced for faster initial response)
        read_timeout_initial = 30  # Initial read timeout (reasonable for normal responses)
        read_timeout_retry = 60   # Read timeout for retries (longer for slow responses)
        
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = retry_delays[min(attempt - 1, len(retry_delays) - 1)]
                    logger.info(f"Retrying TellusTalk API request (attempt {attempt + 1}/{max_retries}) after {delay}s delay...")
                    time.sleep(delay)
                
                # Use shorter timeout for initial attempt, longer for retries
                current_read_timeout = read_timeout_retry if attempt > 0 else read_timeout_initial
                
                # Use tuple for timeout: (connect_timeout, read_timeout)
                response = requests.post(
                    TELLUSTALK_EBOX_ENDPOINT,
                    json=payload,
                    headers=headers,
                    timeout=(connect_timeout, current_read_timeout)
                )
                
                # Check response
                response.raise_for_status()
                
                result = response.json()
                
                logger.info(f"TellusTalk response: job_uuid={result.get('job_uuid')}")
                
                return {
                    "success": True,
                    "job_uuid": result.get("job_uuid"),
                    "job_name": result.get("job_name", job_name),
                    "ebox_job_key": result.get("ebox_job_key"),
                    "members": result.get("members", []),
                    "message": "Document sent for digital signing successfully"
                }
                
            except (requests.exceptions.Timeout, requests.exceptions.ReadTimeout) as e:
                last_exception = e
                logger.warning(f"TellusTalk API timeout (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    # Last attempt failed, raise the exception
                    raise
            except requests.exceptions.RequestException as e:
                # For non-timeout errors, check if we should retry
                # Retry on connection errors, but not on 4xx client errors
                if hasattr(e, 'response') and e.response is not None:
                    status_code = e.response.status_code
                    if 400 <= status_code < 500:
                        # Client error (4xx), don't retry
                        raise
                
                last_exception = e
                logger.warning(f"TellusTalk API error (attempt {attempt + 1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    # Last attempt failed, raise the exception
                    raise
        
        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        
    except requests.RequestException as e:
        error_msg = f"TellusTalk API error: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                error_msg += f" - {error_detail}"
            except:
                error_msg += f" - {e.response.text}"
        logger.error(error_msg)
        raise requests.RequestException(error_msg) from e
    except Exception as e:
        error_msg = f"Error sending to TellusTalk: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg) from e


def format_signer_name(first_name: str, last_name: str) -> str:
    """
    Format signer name from first and last name
    
    Args:
        first_name: First name
        last_name: Last name
        
    Returns:
        Full name formatted as "First Last"
    """
    first = (first_name or "").strip()
    last = (last_name or "").strip()
    return f"{first} {last}".strip()


def create_signer_from_foretradare(person: Dict[str, Any], signature_order: int = 1) -> Dict[str, Any]:
    """
    Create signer dictionary from företrädare (company representative) data
    
    Args:
        person: Dictionary with signer information from UnderskriftForetradare
        signature_order: Order in which this person should sign
        
    Returns:
        Dictionary formatted for TellusTalk API
    """
    first_name = person.get("UnderskriftHandlingTilltalsnamn", "")
    last_name = person.get("UnderskriftHandlingEfternamn", "")
    email = person.get("UnderskriftHandlingEmail", "")
    personal_id = person.get("UnderskriftHandlingPersonnummer", "")
    
    return {
        "name": format_signer_name(first_name, last_name),
        "email": email,
        "personal_id": personal_id,
        "signature_order": signature_order
    }


def create_signer_from_revisor(person: Dict[str, Any], signature_order: int = 1) -> Dict[str, Any]:
    """
    Create signer dictionary from revisor (auditor) data
    
    Args:
        person: Dictionary with signer information from UnderskriftAvRevisor
        signature_order: Order in which this person should sign
        
    Returns:
        Dictionary formatted for TellusTalk API
    """
    first_name = person.get("UnderskriftHandlingTilltalsnamn", "")
    last_name = person.get("UnderskriftHandlingEfternamn", "")
    email = person.get("UnderskriftHandlingEmail", "")
    personal_id = person.get("UnderskriftHandlingPersonnummer", "")
    
    return {
        "name": format_signer_name(first_name, last_name),
        "email": email,
        "personal_id": personal_id,
        "signature_order": signature_order
    }
