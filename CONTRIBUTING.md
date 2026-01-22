# Contributing to Freebox Home Integration

Thank you for your interest in contributing to the Freebox Home integration for Home Assistant! 🎉

## 🌟 How to Contribute

There are many ways to contribute:
- 🐛 Report bugs
- 💡 Suggest new features
- 📝 Improve documentation
- 🔧 Submit code changes
- 🌍 Add or improve translations
- 🧪 Help with testing

## 📋 Before You Start

1. **Check existing issues** - Someone might already be working on it
2. **Discuss major changes** - Open an issue first for significant modifications
3. **Follow code standards** - PEP 8 for style, PEP 257 for docstrings
4. **Test your changes** - Ensure everything works as expected

## 🐛 Reporting Bugs

When reporting bugs, please include:

- **Home Assistant version**: e.g., 2024.1.0
- **Integration version**: e.g., 1.3.1
- **Freebox model**: Delta, Revolution, etc.
- **Description**: Clear description of the issue
- **Steps to reproduce**: How to trigger the bug
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Logs**: Relevant logs from Home Assistant (Settings → System → Logs)

## 💡 Suggesting Features

Feature requests are welcome! Please provide:

- **Use case**: Why is this feature needed?
- **Description**: What should the feature do?
- **Examples**: How would it work?
- **Alternatives**: Other solutions you've considered

## 🔧 Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/freebox_home.git
cd freebox_home
```

### 2. Create Development Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
pip install homeassistant pytest pytest-asyncio black flake8 mypy
```

### 3. Create a Branch

```bash
# Create a feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/bug-description
```

## 📝 Code Standards

### Python Style Guide

- **PEP 8**: Follow Python style guide
- **PEP 257**: Use proper docstrings
- **Type hints**: Use where applicable
- **Line length**: Maximum 88 characters (Black formatter)

### Docstring Format

```python
def example_function(param1: str, param2: int) -> bool:
    """Brief description of the function.
    
    Longer description if needed, explaining the purpose
    and behavior of the function.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When param2 is negative
    """
    pass
```

### Code Quality Checks

```bash
# Format code with Black
black .

# Check style with flake8
flake8 . --max-line-length=88

# Type check with mypy (optional)
mypy . --ignore-missing-imports

# Run tests
python test_changes.py
pytest  # If pytest is installed
```

## 🧪 Testing

### Run Existing Tests

```bash
# Syntax validation
python test_changes.py

# Unit tests (if available)
pytest tests/

# Test in Home Assistant
# Copy integration to config/custom_components/freebox_home
# Restart Home Assistant
# Check logs for errors
```

### Write Tests

- Add tests for new features
- Ensure existing tests still pass
- Test edge cases and error conditions

## 🌍 Translation

To add or improve translations:

1. Navigate to `translations/`
2. Copy `en.json` as a template
3. Translate strings to your language
4. Save as `{language_code}.json` (e.g., `fr.json`, `de.json`)
5. Submit a pull request

## 📤 Submitting Changes

### Commit Messages

Use clear, descriptive commit messages:

```bash
# Good examples
git commit -m "Add support for doorbell notifications"
git commit -m "Fix camera snapshot timeout issue"
git commit -m "Update French translations"

# Format: <type>: <description>
# Types: feat, fix, docs, style, refactor, test, chore
```

### Create Pull Request

1. **Push your branch**:
   ```bash
   git push origin feature/your-feature-name
   ```

2. **Open Pull Request on GitHub**
   - Provide clear title and description
   - Reference related issues (e.g., "Fixes #123")
   - Explain what changed and why
   - Include screenshots for UI changes

3. **Respond to feedback**
   - Address review comments
   - Make requested changes
   - Keep discussion constructive

## ✅ Pull Request Checklist

Before submitting, ensure:

- [ ] Code follows PEP 8 and PEP 257
- [ ] All tests pass
- [ ] New features have tests
- [ ] Documentation updated (README, docstrings)
- [ ] Commit messages are clear
- [ ] No unnecessary files committed
- [ ] Branch is up to date with main

## 🔍 Code Review Process

1. **Automated checks** - GitHub Actions run tests
2. **Maintainer review** - Code quality and functionality
3. **Feedback** - Suggestions for improvements
4. **Approval** - Once everything looks good
5. **Merge** - Changes merged into main branch

## 📚 Resources

- **Home Assistant Development**: https://developers.home-assistant.io/
- **Home Assistant Architecture**: https://developers.home-assistant.io/docs/architecture_index
- **Python Style Guide (PEP 8)**: https://pep8.org/
- **Docstring Guide (PEP 257)**: https://peps.python.org/pep-0257/
- **Freebox API Documentation**: https://dev.freebox.fr/sdk/os/

## 💬 Communication

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and ideas
- **Pull Requests**: Code review and collaboration

## 📜 Code of Conduct

This project follows a code of conduct to ensure a welcoming environment:

- **Be respectful** - Treat everyone with respect
- **Be constructive** - Provide helpful feedback
- **Be patient** - Remember maintainers are volunteers
- **Be inclusive** - Welcome diverse perspectives

Unacceptable behavior includes:
- Harassment or discriminatory comments
- Personal attacks or insults
- Spam or off-topic content
- Sharing private information without permission

## 🙏 Recognition

Contributors are recognized in:
- Git commit history
- Release notes for significant contributions
- Project acknowledgments

## ❓ Questions?

Not sure about something? Don't hesitate to:
- Open an issue with your question
- Start a discussion on GitHub
- Check existing documentation

## 🎉 Thank You!

Every contribution, no matter how small, helps improve this project. Thank you for taking the time to contribute!

---

**Happy coding!** 🚀

*This project is licensed under the Apache License 2.0 - see [LICENSE](LICENSE)*
