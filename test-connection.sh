#!/bin/bash
# Test script for environment variables and connections

echo "🧪 Testing Summare Environment Configuration"
echo "============================================"
echo ""

# Test Backend
echo "📦 Backend Tests:"
echo "-----------------"
cd backend

if [ -f ".env" ]; then
    echo "✅ backend/.env file exists"
    
    # Check if key variables are set
    if grep -q "SUPABASE_URL" .env && grep -q "SUPABASE_ANON_KEY" .env; then
        echo "✅ Supabase credentials found in .env"
    else
        echo "❌ Supabase credentials missing"
    fi
    
    if grep -q "STRIPE_SECRET_KEY" .env; then
        echo "✅ Stripe credentials found"
    else
        echo "❌ Stripe credentials missing"
    fi
else
    echo "❌ backend/.env file not found"
fi

echo ""

# Test Frontend
echo "🎨 Frontend Tests:"
echo "------------------"
cd ../frontend

if [ -f ".env" ]; then
    echo "✅ frontend/.env file exists"
    
    if grep -q "VITE_API_URL" .env; then
        echo "✅ VITE_API_URL found"
    else
        echo "❌ VITE_API_URL missing"
    fi
    
    if grep -q "VITE_STRIPE_PUBLISHABLE_KEY" .env; then
        echo "✅ VITE_STRIPE_PUBLISHABLE_KEY found"
    else
        echo "❌ VITE_STRIPE_PUBLISHABLE_KEY missing"
    fi
else
    echo "❌ frontend/.env file not found"
fi

echo ""
echo "============================================"
echo "✅ Basic checks complete!"
echo ""
echo "Next steps:"
echo "1. Start backend: cd backend && python main.py"
echo "2. Test API: curl http://localhost:8080/api/chat-flow/110"
echo "3. Start frontend: cd frontend && npm run dev"
echo "4. Check browser console for environment variables"


