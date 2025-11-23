#!/bin/bash
# Test script för Bolagsverkets API-endpoints på Railway
# Detta script testar från Railway backend där statiska IP:n 208.77.244.15 finns

# Ange din Railway backend URL här (eller localhost för lokal test)
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"

echo "========================================"
echo "Test av Bolagsverkets API-endpoints"
echo "========================================"
echo ""
echo "Backend URL: $BACKEND_URL"
echo ""

# Test 1: Testa brandväggsåtkomst
echo "----------------------------------------"
echo "Test 1: Brandväggsåtkomst"
echo "----------------------------------------"
echo "Anropar: GET $BACKEND_URL/api/bolagsverket/test-firewall"
echo ""

curl -X GET "$BACKEND_URL/api/bolagsverket/test-firewall" \
  -H "Accept: application/json" \
  | python3 -m json.tool

echo ""
echo ""

# Test 2: Skapa inlämningstoken
echo "----------------------------------------"
echo "Test 2: Skapa inlämningstoken"
echo "----------------------------------------"
echo "Anropar: POST $BACKEND_URL/api/bolagsverket/skapa-inlamningtoken"
echo "Data: orgnr=5566103643, pnr=197212022516"
echo ""

curl -X POST "$BACKEND_URL/api/bolagsverket/skapa-inlamningtoken" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{
    "orgnr": "5566103643",
    "pnr": "197212022516"
  }' \
  | python3 -m json.tool

echo ""
echo ""
echo "========================================"
echo "Test slutfört"
echo "========================================"
echo ""
echo "För att testa mot Railway backend, kör:"
echo "  BACKEND_URL=https://your-railway-url.up.railway.app bash $0"
echo ""

