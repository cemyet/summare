"""
Extract and format company officers (board members, CEO, etc.) from Bolagsverket data
for use in the Signering module
"""
from typing import Dict, List, Any, Optional


def extract_officers_for_signing(company_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract company officers from Bolagsverket company info and format for Signering module
    
    Args:
        company_info: Raw company info from Bolagsverket API
        
    Returns:
        Dict with formatted officer data ready for Signering module
    """
    if not company_info or 'organisationer' not in company_info:
        return {
            'UnderskriftForetradare': [],
            'UnderskriftAvRevisor': []
        }
    
    org = company_info['organisationer'][0]
    officers = org.get('funktionarer', [])
    
    # Map Bolagsverket roles to your Signering module roles
    role_mapping = {
        'Verkställande direktör': 'VD',
        'VD': 'VD',
        'Styrelseledamot': 'Styrelseledamot',
        'Styrelsesuppleant': 'Styrelseledamot',
        'Styrelseordförande': 'Styrelseordförande',
        'Ordförande': 'Styrelseordförande',
        'Revisor': 'Revisor',
        'Revisorssuppleant': 'Revisor'
    }
    
    företrädare_list = []
    revisor_list = []
    
    for officer in officers:
        # Extract name (handle both direct and representerasAv structures)
        fornamn = ''
        efternamn = ''
        personnummer = ''
        
        # Check for direct personnamn (most common)
        if officer.get('personnamn'):
            name = officer['personnamn']
            fornamn = name.get('fornamn', '').strip()
            efternamn = name.get('efternamn', '').strip()
        # Check for representerasAv (auditors represented by a person)
        elif officer.get('representerasAv') and officer['representerasAv'].get('personnamn'):
            name = officer['representerasAv']['personnamn']
            fornamn = name.get('fornamn', '').strip()
            efternamn = name.get('efternamn', '').strip()
        # Check for organisationsnamn (company as auditor)
        elif officer.get('organisationsnamn'):
            efternamn = officer['organisationsnamn'].get('namn', '').strip()
        
        # Extract personnummer (identity number) - check multiple locations
        if officer.get('identitet'):
            personnummer = officer['identitet'].get('identitetsbeteckning', '').strip()
        elif officer.get('representerasAv') and officer['representerasAv'].get('identitet'):
            personnummer = officer['representerasAv']['identitet'].get('identitetsbeteckning', '').strip()
        
        # Extract roles
        officer_roles = []
        if officer.get('funktionarsroller'):
            for role in officer['funktionarsroller']:
                role_text = role.get('klartext', '').strip()
                if role_text:
                    officer_roles.append(role_text)
        
        # Map to Signering module format
        mapped_roles = []
        is_revisor = False
        
        for role in officer_roles:
            # Check if this is a revisor
            if 'revisor' in role.lower():
                is_revisor = True
                mapped_role = role_mapping.get(role, 'Revisor')
            else:
                mapped_role = role_mapping.get(role, role)
            
            if mapped_role not in mapped_roles:
                mapped_roles.append(mapped_role)
        
        # Determine primary role for display
        primary_role = mapped_roles[0] if mapped_roles else ''
        
        # Create officer entry
        officer_entry = {
            'UnderskriftHandlingTilltalsnamn': fornamn,
            'UnderskriftHandlingEfternamn': efternamn,
            'UnderskriftHandlingPersonnummer': personnummer,
            'UnderskriftHandlingEmail': '',  # Not available from Bolagsverket
            'UnderskriftHandlingRoll': primary_role,
            'UnderskriftHandlingDagForUndertecknande': '',  # To be filled by user
            'UnderskriftHandlingAvvikandeMening': None
        }
        
        # Add to appropriate list
        if is_revisor:
            # Add revisor-specific fields
            officer_entry['UnderskriftHandlingTitel'] = 'Auktoriserad revisor'
            officer_entry['UnderskriftRevisorspateckningRevisorHuvudansvarig'] = len(revisor_list) == 0  # First revisor is huvudansvarig
            officer_entry['RevisionsberattelseTyp'] = 'UTAN_MODIFIERING'
            officer_entry['RevisionsberattelseDatum'] = ''
            revisor_list.append(officer_entry)
        else:
            företrädare_list.append(officer_entry)
    
    return {
        'UnderskriftForetradare': företrädare_list,
        'UnderskriftAvRevisor': revisor_list,
        'companyInfo': {
            'companyName': org.get('organisationsnamn', {}).get('namn', '') if org.get('organisationsnamn') else '',
            'organizationNumber': org.get('identitet', {}).get('identitetsbeteckning', '') if org.get('identitet') else ''
        }
    }


def get_officer_summary(company_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get a summary of company officers with counts by role
    
    Args:
        company_info: Raw company info from Bolagsverket API
        
    Returns:
        Dict with officer counts and summary
    """
    extracted = extract_officers_for_signing(company_info)
    
    # Count roles
    role_counts = {}
    for officer in extracted['UnderskriftForetradare']:
        role = officer['UnderskriftHandlingRoll']
        role_counts[role] = role_counts.get(role, 0) + 1
    
    return {
        'totalOfficers': len(extracted['UnderskriftForetradare']),
        'totalRevisors': len(extracted['UnderskriftAvRevisor']),
        'roleCounts': role_counts,
        'officers': extracted
    }


def format_officer_for_display(officer: Dict[str, Any]) -> str:
    """
    Format a single officer for display
    
    Args:
        officer: Officer dict from extract_officers_for_signing
        
    Returns:
        Formatted string for display
    """
    name = f"{officer['UnderskriftHandlingTilltalsnamn']} {officer['UnderskriftHandlingEfternamn']}".strip()
    role = officer['UnderskriftHandlingRoll']
    personnummer = officer.get('UnderskriftHandlingPersonnummer', '')
    
    if personnummer:
        return f"{name} ({personnummer}) - {role}"
    else:
        return f"{name} - {role}"


# Example usage for testing
if __name__ == "__main__":
    import asyncio
    from bolagsverket_service import BolagsverketService
    
    async def test_extraction():
        service = BolagsverketService()
        
        # Test with a real organization number
        org_number = input("Enter organization number (10 digits): ").strip().replace('-', '').replace(' ', '')
        
        print(f"\n🔍 Fetching company info for {org_number}...")
        company_info = await service.get_company_info(org_number)
        
        if not company_info:
            print("❌ No company info found")
            return
        
        print("\n📋 Extracting officers for Signering module...")
        extracted = extract_officers_for_signing(company_info)
        
        print(f"\n✅ FOUND:")
        print(f"   Företrädare: {len(extracted['UnderskriftForetradare'])}")
        print(f"   Revisorer: {len(extracted['UnderskriftAvRevisor'])}")
        
        print(f"\n👥 FÖRETRÄDARE:")
        for i, officer in enumerate(extracted['UnderskriftForetradare'], 1):
            print(f"   {i}. {format_officer_for_display(officer)}")
        
        print(f"\n✍️ REVISORER:")
        for i, revisor in enumerate(extracted['UnderskriftAvRevisor'], 1):
            print(f"   {i}. {format_officer_for_display(revisor)}")
            if revisor.get('UnderskriftRevisorspateckningRevisorHuvudansvarig'):
                print(f"      (Huvudansvarig)")
        
        # Show summary
        summary = get_officer_summary(company_info)
        print(f"\n📊 SUMMARY:")
        print(f"   Total officers: {summary['totalOfficers']}")
        print(f"   Total revisors: {summary['totalRevisors']}")
        if summary['roleCounts']:
            print(f"   Role breakdown:")
            for role, count in summary['roleCounts'].items():
                print(f"      - {role}: {count}")
    
    asyncio.run(test_extraction())


