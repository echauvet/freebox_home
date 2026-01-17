#!/bin/bash
#
# @file generate_docs.sh
# @brief Generate Doxygen documentation for Freebox Home integration
# @version 1.0
#
# Usage: ./generate_docs.sh [options]
# Options:
#   --html      Generate HTML documentation (default)
#   --xml       Generate XML documentation
#   --all       Generate all formats
#   --clean     Clean previous documentation
#   --open      Open HTML documentation in browser
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DOCS_OUTPUT="${SCRIPT_DIR}/docs"
DOXYFILE="${SCRIPT_DIR}/Doxyfile"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Doxygen is installed
if ! command -v doxygen &> /dev/null; then
    echo -e "${RED}Error: Doxygen is not installed${NC}"
    echo "Install it with: sudo apt-get install doxygen"
    exit 1
fi

# Parse arguments
GENERATE_HTML=true
GENERATE_XML=false
GENERATE_ALL=false
CLEAN=false
OPEN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --html) GENERATE_HTML=true; shift ;;
        --xml) GENERATE_XML=true; shift ;;
        --all) GENERATE_ALL=true; shift ;;
        --clean) CLEAN=true; shift ;;
        --open) OPEN=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Clean previous documentation if requested
if [ "$CLEAN" = true ]; then
    echo -e "${YELLOW}Cleaning previous documentation...${NC}"
    rm -rf "${DOCS_OUTPUT}"
fi

# Create temporary Doxyfile with output settings
TEMP_DOXYFILE=$(mktemp)
cp "${DOXYFILE}" "${TEMP_DOXYFILE}"

if [ "$GENERATE_ALL" = true ]; then
    GENERATE_HTML=true
    GENERATE_XML=true
fi

# Update output settings in temporary Doxyfile
sed -i "s|^OUTPUT_DIRECTORY.*|OUTPUT_DIRECTORY = ${DOCS_OUTPUT}|" "${TEMP_DOXYFILE}"
sed -i "s|^GENERATE_HTML.*|GENERATE_HTML = $([ "$GENERATE_HTML" = true ] && echo "YES" || echo "NO")|" "${TEMP_DOXYFILE}"
sed -i "s|^GENERATE_XML.*|GENERATE_XML = $([ "$GENERATE_XML" = true ] && echo "YES" || echo "NO")|" "${TEMP_DOXYFILE}"

# Generate documentation
echo -e "${YELLOW}Generating Doxygen documentation...${NC}"
echo "Using Doxygen version: $(doxygen --version)"
echo "Output directory: ${DOCS_OUTPUT}"

cd "${SCRIPT_DIR}"
doxygen "${TEMP_DOXYFILE}"

# Clean up
rm -f "${TEMP_DOXYFILE}"

# Report success
echo -e "${GREEN}Documentation generated successfully!${NC}"
echo "Output location: ${DOCS_OUTPUT}"

if [ "$GENERATE_HTML" = true ]; then
    HTML_INDEX="${DOCS_OUTPUT}/html/index.html"
    echo -e "${GREEN}HTML documentation: ${HTML_INDEX}${NC}"
    
    if [ "$OPEN" = true ]; then
        if command -v xdg-open &> /dev/null; then
            xdg-open "${HTML_INDEX}" &
        elif command -v open &> /dev/null; then
            open "${HTML_INDEX}" &
        fi
    fi
fi

if [ "$GENERATE_XML" = true ]; then
    echo -e "${GREEN}XML documentation: ${DOCS_OUTPUT}/xml/${NC}"
fi

echo -e "${GREEN}✓ Documentation generation complete!${NC}"
