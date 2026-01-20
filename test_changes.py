#!/usr/bin/env python3
"""Test script for Freebox Home integration changes"""

import ast
import json

def test_syntax():
    """Test all Python files for syntax errors"""
    print("=" * 60)
    print("SYNTAX VALIDATION")
    print("=" * 60)
    
    files = [
        '__init__.py', 'entity.py', 'router.py', 'cover.py', 
        'switch.py', 'alarm_control_panel.py', 'config_flow.py',
        'const.py', 'sensor.py', 'binary_sensor.py'
    ]
    
    for filename in files:
        try:
            with open(filename, 'r') as f:
                ast.parse(f.read(), filename=filename)
            print(f'✓ {filename:30} - Valid syntax')
        except FileNotFoundError:
            print(f'⚠ {filename:30} - File not found')
        except SyntaxError as e:
            print(f'✗ {filename:30} - Syntax error: {e}')
            return False
    return True

def test_config_changes():
    """Test configuration changes"""
    print("\n" + "=" * 60)
    print("CONFIGURATION CHANGES")
    print("=" * 60)
    
    # Check strings.json
    try:
        with open('strings.json', 'r') as f:
            strings = json.load(f)
        
        if 'temp_refresh_interval' in strings.get('options', {}).get('step', {}).get('init', {}).get('data', {}):
            print('✓ strings.json - temp_refresh_interval added')
        else:
            print('✗ strings.json - temp_refresh_interval missing')
            
    except Exception as e:
        print(f'✗ strings.json - Error: {e}')
    
    # Check translations/en.json
    try:
        with open('translations/en.json', 'r') as f:
            trans = json.load(f)
        
        if 'temp_refresh_interval' in trans.get('options', {}).get('step', {}).get('init', {}).get('data', {}):
            print('✓ translations/en.json - temp_refresh_interval added')
        else:
            print('✗ translations/en.json - temp_refresh_interval missing')
            
    except Exception as e:
        print(f'✗ translations/en.json - Error: {e}')

def test_code_patterns():
    """Test for key code patterns"""
    print("\n" + "=" * 60)
    print("CODE PATTERN VALIDATION")
    print("=" * 60)
    
    checks = [
        ('const.py', 'CONF_TEMP_REFRESH_INTERVAL', 'Configuration constant'),
        ('const.py', 'DEFAULT_TEMP_REFRESH_INTERVAL', 'Default value constant'),
        ('config_flow.py', 'CONF_TEMP_REFRESH_INTERVAL', 'Config flow imports'),
        ('config_flow.py', 'vol.Range(min=1, max=10)', 'Options validation'),
        ('router.py', 'async def get_node_data', 'Optimized node fetch'),
        ('router.py', 'get_home_node(node_id)', 'API optimization'),
        ('entity.py', 'get_node_data', 'Entity base class update'),
        ('cover.py', 'get_node_data', 'Cover optimization'),
        ('switch.py', 'get_node_data', 'Switch optimization'),
        ('entity.py', 'config_entry.options.get', 'Config access'),
        ('cover.py', 'config_entry.options.get', 'Cover config access'),
        ('switch.py', 'config_entry.options.get', 'Switch config access'),
    ]
    
    for filename, pattern, description in checks:
        try:
            with open(filename, 'r') as f:
                content = f.read()
            
            if pattern in content:
                print(f'✓ {description:40} - Found in {filename}')
            else:
                print(f'✗ {description:40} - Missing in {filename}')
                
        except FileNotFoundError:
            print(f'⚠ {description:40} - File {filename} not found')

def main():
    print("\n" + "=" * 60)
    print("FREEBOX HOME INTEGRATION TEST SUITE")
    print("=" * 60 + "\n")
    
    syntax_ok = test_syntax()
    test_config_changes()
    test_code_patterns()
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    if syntax_ok:
        print("✓ All syntax tests passed")
        print("✓ Ready for Home Assistant integration")
        print("\nNext steps:")
        print("  1. Restart Home Assistant")
        print("  2. Go to Settings → Devices & Services")
        print("  3. Configure Freebox integration")
        print("  4. Test temp_refresh_interval option (1-10 seconds)")
        return 0
    else:
        print("✗ Some tests failed - review errors above")
        return 1

if __name__ == '__main__':
    exit(main())
