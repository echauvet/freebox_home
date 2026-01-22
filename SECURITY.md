# Security Policy

## Supported Versions

We actively support the following versions of the Freebox Home integration:

| Version | Supported          |
| ------- | ------------------ |
| 1.3.x   | :white_check_mark: |
| 1.2.x   | :white_check_mark: |
| 1.1.x   | :x:                |
| < 1.1   | :x:                |

## Reporting a Vulnerability

We take the security of the Freebox Home integration seriously. If you discover a security vulnerability, please follow these steps:

### 1. Do Not Publicly Disclose

Please do not publicly disclose the vulnerability until it has been addressed. This includes:
- GitHub issues
- Public discussions
- Social media
- Forums

### 2. Report Privately

Report security vulnerabilities through one of these methods:

**Preferred**: Use GitHub's [Security Advisories](https://github.com/echauvet/freebox_home/security/advisories/new)

**Alternative**: Email the maintainers directly with:
- A clear description of the vulnerability
- Steps to reproduce the issue
- Potential impact and severity assessment
- Any suggested fixes (if available)

### 3. What to Expect

After you submit a vulnerability report:

- **Acknowledgment**: We'll acknowledge receipt within 48 hours
- **Assessment**: We'll assess the vulnerability and determine severity within 5 business days
- **Updates**: We'll keep you informed about our progress
- **Fix**: We'll work on a fix and release timeline
- **Credit**: With your permission, we'll credit you in the security advisory

### 4. Disclosure Timeline

- **Critical vulnerabilities**: Fixed within 7 days
- **High severity**: Fixed within 14 days
- **Medium/Low severity**: Fixed in next scheduled release

After a fix is released, we'll:
1. Publish a security advisory
2. Update the changelog
3. Notify users through GitHub releases

## Security Best Practices

When using this integration:

### Home Network Security

1. **Secure Your Home Assistant Instance**:
   - Use strong passwords
   - Enable two-factor authentication
   - Keep Home Assistant updated
   - Use HTTPS for remote access

2. **Freebox Security**:
   - Keep Freebox firmware updated
   - Use strong Freebox admin password
   - Review authorized API applications regularly

3. **Network Isolation**:
   - Consider using VLANs for IoT devices
   - Use firewall rules to restrict access
   - Disable unnecessary Freebox services

### API Token Security

- **Never share** your Freebox API token publicly
- **Don't commit** tokens or credentials to version control
- **Rotate tokens** regularly
- **Revoke** unused or compromised tokens immediately

### Integration Configuration

- Review integration permissions regularly
- Only enable needed entities
- Use Home Assistant's user access controls
- Monitor integration logs for suspicious activity

## Known Security Considerations

### API Authentication

This integration uses the Freebox API which requires:
- Local network access
- One-time authorization on Freebox device
- Token-based authentication

The API tokens are stored securely in Home Assistant's configuration storage.

### Data Privacy

- All communication is local (no cloud services)
- Camera snapshots are processed locally
- No data is transmitted outside your network
- Logs may contain device names and states (review before sharing)

### Dependencies

We rely on these external libraries:
- `freebox-api` - Official Freebox API Python library

We monitor these dependencies for security issues and update promptly.

## Security Updates

Security updates are released as patch versions (e.g., 1.3.1 → 1.3.2) and clearly marked in:
- GitHub releases
- `RELEASE_NOTES.md`
- Security advisories

## Vulnerability History

No security vulnerabilities have been reported or discovered to date.

## Contact

For security concerns that don't involve vulnerabilities (questions, best practices, etc.):
- [GitHub Discussions](https://github.com/echauvet/freebox_home/discussions)
- [GitHub Issues](https://github.com/echauvet/freebox_home/issues) (for non-sensitive topics)

## Acknowledgments

We appreciate security researchers and users who responsibly disclose vulnerabilities. Contributors will be acknowledged in:
- Security advisories
- Release notes
- This document (with permission)

---

**Thank you for helping keep Freebox Home integration and our users safe!**

*Last updated: January 22, 2026*
