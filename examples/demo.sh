#!/usr/bin/env bash
# SafeClaw Demo — Run all commands against the sample repo
set -e

echo "=== SafeClaw Demo ==="
echo ""

echo "📋 Current Policy:"
safeclaw policy
echo ""

echo "🔍 Scanning for TODOs..."
safeclaw todo ./examples/sample-repo/
echo ""

echo "📊 Summarizing build log..."
safeclaw summarize ./examples/sample-repo/build.log
echo ""

echo "🔐 Scanning for secrets..."
safeclaw secrets ./examples/sample-repo/
echo ""

echo "📦 Checking dependencies..."
safeclaw deps .
echo ""

echo "📈 Repository stats..."
safeclaw stats ./examples/sample-repo/
echo ""

echo "📝 Recent audit log:"
safeclaw audit
echo ""

echo "✅ Demo complete!"
