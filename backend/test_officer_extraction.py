#!/usr/bin/env python3
"""
Simple test script for officer extraction
"""
import asyncio
import json
import sys

# Add the backend directory to the path
sys.path.insert(0, '/Users/cem/Desktop/Summare/backend')

from services.bolagsverket_officers_extractor import extract_officers_for_signing

async def test_with_mock_data():
    """Test with mock Bolagsverket data"""
    
    # Example mock data structure from Bolagsverket
    mock_company_info = {
        'organisationer': [{
            'identitet': {
                'typ': {'klartext': 'Aktiebolag'},
                'identitetsbeteckning': '5560123456'
            },
            'organisationsnamn': {
                'typ': {'klartext': 'Företagsnamn'},
                'namn': 'Test AB'
            },
            'funktionarer': [
                {
                    'personnamn': {
                        'fornamn': 'Johan',
                        'efternamn': 'Burénius'
                    },
                    'identitet': {
                        'identitetsbeteckning': '198012011234'
                    },
                    'funktionarsroller': [
                        {'klartext': 'Styrelseledamot'}
                    ]
                },
                {
                    'personnamn': {
                        'fornamn': 'John Roger',
                        'efternamn': 'Holtback'
                    },
                    'identitet': {
                        'identitetsbeteckning': '197505155678'
                    },
                    'funktionarsroller': [
                        {'klartext': 'Styrelseordförande'}
                    ]
                },
                {
                    'personnamn': {
                        'fornamn': 'Anna',
                        'efternamn': 'Svensson'
                    },
                    'identitet': {
                        'identitetsbeteckning': '198503209876'
                    },
                    'funktionarsroller': [
                        {'klartext': 'Verkställande direktör'}
                    ]
                },
                {
                    'personnamn': {
                        'fornamn': 'Lars',
                        'efternamn': 'Andersson'
                    },
                    'identitet': {
                        'identitetsbeteckning': '197008154321'
                    },
                    'funktionarsroller': [
                        {'klartext': 'Revisor'}
                    ]
                },
                {
                    'organisationsnamn': {
                        'namn': 'PwC Sverige AB'
                    },
                    'identitet': {
                        'identitetsbeteckning': '5569876543'
                    },
                    'funktionarsroller': [
                        {'klartext': 'Revisor'}
                    ]
                }
            ]
        }]
    }
    
    print("🧪 TESTING OFFICER EXTRACTION")
    print("=" * 60)
    
    # Extract officers
    result = extract_officers_for_signing(mock_company_info)
    
    # Display results
    print(f"\n📊 COMPANY INFO:")
    print(f"   Name: {result['companyInfo']['companyName']}")
    print(f"   Org Number: {result['companyInfo']['organizationNumber']}")
    
    print(f"\n👥 FÖRETRÄDARE ({len(result['UnderskriftForetradare'])} found):")
    print("-" * 60)
    for i, officer in enumerate(result['UnderskriftForetradare'], 1):
        print(f"\n   {i}. {officer['UnderskriftHandlingTilltalsnamn']} {officer['UnderskriftHandlingEfternamn']}")
        print(f"      Personnummer: {officer['UnderskriftHandlingPersonnummer']}")
        print(f"      Roll: {officer['UnderskriftHandlingRoll']}")
        print(f"      Email: {officer['UnderskriftHandlingEmail'] or '(tom)'}")
    
    print(f"\n✍️  REVISORER ({len(result['UnderskriftAvRevisor'])} found):")
    print("-" * 60)
    for i, revisor in enumerate(result['UnderskriftAvRevisor'], 1):
        print(f"\n   {i}. {revisor['UnderskriftHandlingTilltalsnamn']} {revisor['UnderskriftHandlingEfternamn']}")
        print(f"      Personnummer: {revisor.get('UnderskriftHandlingPersonnummer', 'N/A')}")
        print(f"      Titel: {revisor.get('UnderskriftHandlingTitel', 'N/A')}")
        print(f"      Huvudansvarig: {'Ja' if revisor.get('UnderskriftRevisorspateckningRevisorHuvudansvarig') else 'Nej'}")
    
    print(f"\n📄 FULL JSON OUTPUT:")
    print("-" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    print(f"\n✅ TEST COMPLETED")

if __name__ == "__main__":
    asyncio.run(test_with_mock_data())


