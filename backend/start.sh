#!/bin/bash

echo "🚀 Startar Raketrapport Backend API..."

# Kontrollera om virtual environment finns
if [ ! -d "venv" ]; then
    echo "📦 Skapar virtual environment..."
    python3 -m venv venv
fi

# Aktivera virtual environment
echo "🔧 Aktiverar virtual environment..."
source venv/bin/activate

# Installera dependencies
echo "📚 Installerar dependencies..."
pip install -r requirements.txt

# Starta servern
echo "🌐 Startar FastAPI server..."
python main.py 