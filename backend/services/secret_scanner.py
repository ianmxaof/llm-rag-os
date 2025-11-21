"""
Secret Scanner Service
----------------------
Integration with TruffleHog for secret scanning.
"""

import os
import subprocess
from typing import Dict, List, Optional
from pathlib import Path


class SecretScanner:
    """Service for scanning content for secrets using TruffleHog."""
    
    def __init__(self, enabled: bool = True):
        """
        Initialize secret scanner.
        
        Args:
            enabled: Whether secret scanning is enabled
        """
        self.enabled = enabled and os.getenv("TRUFFLEHOG_ENABLED", "false").lower() == "true"
        self.trufflehog_path = os.getenv("TRUFFLEHOG_PATH", "trufflehog")
        
    def scan_text(self, text: str, source_url: Optional[str] = None) -> Dict:
        """
        Scan text content for secrets.
        
        Args:
            text: Text content to scan
            source_url: Optional source URL for context
            
        Returns:
            Dict with scan results:
            - found: bool
            - secrets: List[Dict] (if found)
            - redacted_text: str (with secrets redacted)
        """
        if not self.enabled:
            return {
                "found": False,
                "secrets": [],
                "redacted_text": text,
            }
        
        # Write text to temp file for scanning
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(text)
            temp_path = f.name
        
        try:
            # Run TruffleHog
            result = subprocess.run(
                [self.trufflehog_path, "filesystem", "--directory", str(Path(temp_path).parent)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            secrets = []
            if result.returncode == 0 and result.stdout:
                # Parse TruffleHog output (JSON format)
                import json
                try:
                    output = json.loads(result.stdout)
                    if isinstance(output, list):
                        secrets = output
                    elif isinstance(output, dict) and "findings" in output:
                        secrets = output["findings"]
                except json.JSONDecodeError:
                    # Try to parse line-by-line
                    for line in result.stdout.split("\n"):
                        if line.strip():
                            try:
                                secrets.append(json.loads(line))
                            except:
                                pass
            
            # Redact secrets from text
            redacted_text = text
            for secret in secrets:
                if "detector" in secret and "raw" in secret:
                    redacted_text = redacted_text.replace(secret["raw"], "[REDACTED]")
            
            return {
                "found": len(secrets) > 0,
                "secrets": secrets,
                "redacted_text": redacted_text,
            }
        except FileNotFoundError:
            print("[WARN] TruffleHog not found. Install with: pip install trufflehog")
            return {
                "found": False,
                "secrets": [],
                "redacted_text": text,
            }
        except Exception as e:
            print(f"[WARN] Secret scanning failed: {e}")
            return {
                "found": False,
                "secrets": [],
                "redacted_text": text,
            }
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass
    
    def send_alert(self, secrets: List[Dict], source_url: Optional[str] = None):
        """
        Send alert about found secrets.
        
        Args:
            secrets: List of found secrets
            source_url: Source URL where secrets were found
        """
        if not secrets:
            return
        
        webhook_url = os.getenv("SECRET_ALERT_WEBHOOK", "")
        if not webhook_url:
            print(f"[ALERT] Secrets found in {source_url}: {len(secrets)} secrets detected")
            return
        
        # Send webhook alert
        try:
            import requests
            requests.post(
                webhook_url,
                json={
                    "text": f"🚨 Secrets detected in {source_url}",
                    "secrets_count": len(secrets),
                    "secrets": secrets[:5],  # Limit to first 5
                },
                timeout=10,
            )
        except Exception as e:
            print(f"[WARN] Failed to send secret alert: {e}")

