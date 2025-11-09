#!/bin/bash
# Script to pull environment variables from Railway and create .env file

echo "🔐 Make sure you're logged in to Railway (run 'railway login' first)"
echo "📦 Make sure you're linked to the project (run 'railway link' if needed)"
echo ""
echo "📥 Pulling environment variables from Railway..."
echo ""

# Pull variables and format as .env file
railway variables --json | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    if isinstance(data, dict) and 'variables' in data:
        vars = data['variables']
    elif isinstance(data, list):
        vars = data
    else:
        vars = []
    
    # Group variables by category
    categories = {
        'Supabase': ['SUPABASE'],
        'Stripe': ['STRIPE'],
        'Bolagsverket': ['BOLAGSVERKET'],
        'TellusTalk': ['TELLUSTALK'],
        'Email': ['EMAIL', 'SMTP', 'RESEND', 'SENDGRID'],
        'Server': ['PORT', 'PYTHON_VERSION']
    }
    
    output = []
    for category, prefixes in categories.items():
        output.append(f'# {category} Configuration')
        for var in vars:
            if isinstance(var, dict):
                key = var.get('name', '')
                value = var.get('value', '')
            else:
                key = str(var)
                value = ''
            
            if any(key.startswith(p) for p in prefixes):
                output.append(f'{key}={value}')
        output.append('')
    
    # Add any remaining variables
    remaining = []
    for var in vars:
        if isinstance(var, dict):
            key = var.get('name', '')
        else:
            key = str(var)
        if not any(key.startswith(p) for prefix_list in categories.values() for p in prefix_list):
            if isinstance(var, dict):
                value = var.get('value', '')
                remaining.append(f'{key}={value}')
    
    if remaining:
        output.append('# Other Configuration')
        output.extend(remaining)
    
    print('\n'.join(output))
except Exception as e:
    print(f'# Error parsing Railway variables: {e}', file=sys.stderr)
    print('# Please run: railway variables')
" > .env

echo "✅ Environment variables saved to backend/.env"
echo ""
echo "⚠️  Please review the .env file and ensure all values are correct"
