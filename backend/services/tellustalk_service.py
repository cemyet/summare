"""
TellusTalk eBox API Service for Digital Signatures
Sends PDFs for digital signing using TellusTalk's WebSign API
"""
import os
import base64
import requests
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# TellusTalk API Configuration
TELLUSTALK_BASE_URL = "https://k8api.tellustalk.com"
TELLUSTALK_WEBSIGN_ENDPOINT = f"{TELLUSTALK_BASE_URL}/ebox/websign/v1"

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


def send_pdf_for_signing(
    pdf_bytes: bytes,
    signers: List[Dict[str, Any]],
    job_name: str,
    success_redirect_url: Optional[str] = None,
    fail_redirect_url: Optional[str] = None,
    report_to_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Send PDF document to TellusTalk for digital signing
    
    Args:
        pdf_bytes: PDF file as bytes
        signers: List of signer dictionaries with:
            - name: Full name of signer
            - email: Email address for signing invitation
            - signature_methods: List of signature methods (e.g., [{"type": "bankid"}])
        job_name: Name of the signing job
        success_redirect_url: URL to redirect after successful signing (optional)
        fail_redirect_url: URL to redirect after failed signing (optional)
        report_to_url: Callback URL for job status updates (optional)
        
    Returns:
        Dictionary with:
            - success: Boolean indicating if request was successful
            - job_uuid: Unique identifier for the signing job
            - redirect_url: URL for recipients to access the job
            - job_name: Name of the job
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
        
        # Build request payload
        payload = {
            "attachment": {
                "name": "arsredovisning.pdf",
                "content_transfer_encoding": "base64",
                "content_type": "application/pdf",
                "payload": pdf_base64
            },
            "job_name": job_name,
        }
        
        # Add members (signers) - TellusTalk supports multiple signers
        # Note: API structure based on TellusTalk WebSign API documentation
        # If API uses different structure (e.g., "member" singular or different field name),
        # this may need adjustment based on actual API response
        payload["members"] = []
        for signer in signers:
            member = {
                "name": signer.get("name", ""),
                "email": signer.get("email", ""),
                "signature_methods": signer.get("signature_methods", [{"type": "bankid"}])
            }
            payload["members"].append(member)
        
        # Add redirect URLs - success_redirect_url is required by TellusTalk API
        # Provide default if not specified
        payload["success_redirect_url"] = success_redirect_url or "https://summare.se/app?signing=success"
        if fail_redirect_url:
            payload["fail_redirect_url"] = fail_redirect_url
        
        # Add optional callback URL
        if report_to_url:
            payload["report_to"] = {
                "url": report_to_url,
                "events": ["job.completed", "job.failed"]
            }
        
        # Prepare request headers
        headers = {
            "Authorization": create_basic_auth_header(username, password),
            "Content-Type": "application/json"
        }
        
        # Make API request
        logger.info(f"Sending PDF to TellusTalk for signing: {job_name}")
        logger.info(f"Number of signers: {len(signers)}")
        
        response = requests.post(
            TELLUSTALK_WEBSIGN_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        # Check response
        response.raise_for_status()
        
        result = response.json()
        
        logger.info(f"TellusTalk response: job_uuid={result.get('job_uuid')}")
        
        return {
            "success": True,
            "job_uuid": result.get("job_uuid"),
            "redirect_url": result.get("redirect_url"),
            "job_name": result.get("job_name", job_name),
            "message": "Document sent for digital signing successfully"
        }
        
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


def create_signer_from_foretradare(person: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create signer dictionary from företrädare (company representative) data
    
    Args:
        person: Dictionary with signer information from UnderskriftForetradare
        
    Returns:
        Dictionary formatted for TellusTalk API
    """
    first_name = person.get("UnderskriftHandlingTilltalsnamn", "")
    last_name = person.get("UnderskriftHandlingEfternamn", "")
    email = person.get("UnderskriftHandlingEmail", "")
    
    return {
        "name": format_signer_name(first_name, last_name),
        "email": email,
        "signature_methods": [{"type": "bankid"}]
    }


def create_signer_from_revisor(person: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create signer dictionary from revisor (auditor) data
    
    Args:
        person: Dictionary with signer information from UnderskriftAvRevisor
        
    Returns:
        Dictionary formatted for TellusTalk API
    """
    first_name = person.get("UnderskriftHandlingTilltalsnamn", "")
    last_name = person.get("UnderskriftHandlingEfternamn", "")
    email = person.get("UnderskriftHandlingEmail", "")
    
    return {
        "name": format_signer_name(first_name, last_name),
        "email": email,
        "signature_methods": [{"type": "bankid"}]
    }

